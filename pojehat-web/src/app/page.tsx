'use client';

import { ManualUpload } from '@/components/manual-upload';
import { ThemeToggle } from '@/components/theme-toggle';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { askMechanicAgent, decodeVin } from '@/lib/api';
import { AlertTriangle, Car, Search, Send, ShieldCheck, User, Wrench } from 'lucide-react';
import Image from 'next/image';
import React, { useEffect, useRef, useState } from 'react';

// Static Asset Imports (Guaranteed Resolution)
import logoMain from '@/assets/pojehat-logo.png';
import logoSidebarLight from '@/assets/pojehat-left-pane-square-logo500light.png';
import logoSidebarDark from '@/assets/pojehat-left-pane-square-logo500.png';
import logoBanner from '@/assets/poje-main-banner-logo-250.png';
import logoTrans from '@/assets/pojehat-logo-trans-500.png';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { useTheme } from 'next-themes';
import { formatDiagnosticResponse } from '@/utils/responseFormatter';

interface Message {
  role: 'user' | 'bot';
  content: string;
  isDtc?: boolean;
}

interface VinData {
  vin: string;
  valid: boolean;
  make?: string;
  model_year?: string;
  wmi?: string;
  country?: string;
  vehicle_context_suggestion?: string;
  message?: string;
  confidence?: string;
  technical_brief?: string;      // ADD: Instant spec brief from vehicle_specs.py
  has_rag_followup?: boolean;    // ADD: True when RAG follow-up bubble should fire
}

const isArabic = (text: any): boolean => {
  if (typeof text === 'string') return /[\u0600-\u06FF]/.test(text);
  if (Array.isArray(text)) return text.some(isArabic);
  if (typeof text === 'object' && text?.props?.children) return isArabic(text.props.children);
  return false;
};

export default function PojehatDashboard() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [vehicle, setVehicle] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [dtcLoading, setDtcLoading] = useState(false);
  const [vin, setVin] = useState('');
  const [vinLoading, setVinLoading] = useState(false);
  const [vinError, setVinError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Prevent hydration mismatch: SSR/First client render must be identical
  const logoSrc = (mounted && resolvedTheme === 'dark')
    ? logoSidebarLight.src
    : logoSidebarDark.src;

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);
    try {
      const result = await askMechanicAgent(userMsg, vehicle);
      setMessages((prev) => [...prev, { role: 'bot', content: result.response }]);
    } catch (error) {
      console.error(error);
      const is429 = error instanceof Error &&
        (error.message.includes('429') ||
         error.message.includes('rate_limit'));
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          content: is429
            ? 'أنت بتبعت requests كتير أوي — استنى شوية وجرب تاني.'
            : 'Error: Failed to connect to Pojehat engine.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  /*
# Task: Aesthetic & Structural Finetuning

## Part 1: Top Banner Refinement
- [x] Increase banner capsule vertical padding (py-3.5) <!-- id: 51 -->
- [ ] Reduce banner font size (-15%) <!-- id: 58 -->
- [ ] Verify banner content breathable-ness <!-- id: 52 -->

## Part 2: Side Pane Structural & Color Update
- [x] Increase side-pane width (w-85) <!-- id: 53 -->
- [ ] Increase side-pane internal horizontal padding (px-8) <!-- id: 59 -->
- [x] Change all side-pane borders to #a48fa3 <!-- id: 54 -->

## Part 3: Chat Panel & Response Aesthetics
- [x] Implement subtle cell borders for diagnostic tables <!-- id: 60 -->
- [x] Fix grounding bar injection (using .strip()) <!-- id: 55 -->
- [ ] Add subtle left-aligned underlines to main titles in response <!-- id: 61 -->
- [ ] Increase symbol scaling (○, ◆, ▸, ⚠) and DTC capsule roundness <!-- id: 62 -->
- [ ] Implement robust RTL/LTR logic for individual response elements <!-- id: 63 -->

## Part 4: Verification
- [ ] Verify final visual balance and RTL/LTR consistency in browser <!-- id: 56 -->
- [ ] Update walkthrough with screenshots of final UI state <!-- id: 57 -->
*/
  const handleDtcSubmit = async () => {
    if (!errorCode.trim()) return;
    const code = errorCode.trim().toUpperCase();
    const dtcQuery = [
      `DTC FAULT DIAGNOSIS REQUEST: ${code}`,
      vehicle ? `Vehicle: ${vehicle}` : 'Vehicle: Not specified',
      'Provide a full structured diagnostic report: root cause analysis, circuit/component specs, safe test procedure, and systematic fix procedure.',
    ].join('\n');
    const userBubble = `\u{1F534} DTC: ${code}${vehicle ? `  |  ${vehicle}` : ''}`;
    setMessages((prev) => [...prev, { role: 'user', content: userBubble, isDtc: true }]);
    setErrorCode('');
    setDtcLoading(true);
    try {
      const result = await askMechanicAgent(dtcQuery, vehicle);
      setMessages((prev) => [...prev, { role: 'bot', content: result.response }]);
    } catch (error) {
      console.error("DTC Diagnosis Error:", error);
      const errorMsg = error instanceof Error ? error.message : String(error);
      setMessages((prev) => [
        ...prev,
        { 
          role: 'bot', 
          content: `Error: Failed to run DTC diagnosis. (${errorMsg})\n\nCheck your Railway backend status and ensure NEXT_PUBLIC_API_URL is set correctly on Vercel.` 
        },
      ]);
    }
 finally {
      setDtcLoading(false);
    }
  };

  const buildVinChatMessage = (data: VinData): string => {
    if (!data.valid && !data.make) {
      return `\u{1F50D} **VIN Lookup: ${data.vin}**\n\n\u274C ${data.message ?? 'Unknown error'}`;
    }

    // If backend returned a rich technical brief, use it directly.
    // Otherwise fall back to the short summary format.
    if (data.technical_brief) {
      return data.technical_brief;
    }

    const badge =
      data.confidence === 'high' ? '\u2705' :
      data.confidence === 'medium' ? '\u{1F7E1}' : '\u26A0\uFE0F';
    const lines = [
      `\u{1F50D} **VIN Decoded: \`${data.vin}\`**`,
      '',
      `${badge} **${data.make ?? 'Unknown'}** \u00B7 ${data.model_year ?? 'Year unknown'}`,
      `\uD83C\uDF0D Origin: ${data.country ?? 'Unknown'} \u00B7 WMI: \`${data.wmi ?? '---'}\``,
      '',
      `\uD83D\uDE97 Vehicle context set to: **${data.vehicle_context_suggestion ?? '\u2014'}**`,
      '',
      `_${data.message ?? ''}_`,
    ];
    return lines.join('\n');
  };

  const handleKnowledgeAudit = async () => {
    setLoading(true);
    const auditQuery =
      "analyze your knowledge base and rate your confidence " +
      "by domain, list what vehicles you have OEM data for, " +
      "and identify critical gaps";
    setMessages((prev) => [
      ...prev,
      { role: "user", content: "Knowledge Base Audit" },
    ]);
    try {
      const result = await askMechanicAgent(auditQuery, "");
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: result.response },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "Audit failed. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleVinDecode = async () => {
    const trimmed = vin.trim().toUpperCase();
    if (trimmed.length !== 17) {
      setVinError('VIN must be exactly 17 characters');
      return;
    }
    setVinError('');
    setVinLoading(true);
    try {
      const data: VinData = await decodeVin(trimmed);

      // Auto-populate vehicle context on successful decode
      if (data.valid && data.vehicle_context_suggestion) {
        setVehicle(data.vehicle_context_suggestion);
      }

      // Bubble 1 — instant brief (technical_brief if available, else short summary)
      setMessages((prev) => [
        ...prev,
        { role: 'bot', content: buildVinChatMessage(data) },
      ]);
      setVin('');

      // Bubble 2 — async RAG enrichment (fires only when spec was matched)
      if (data.has_rag_followup && data.vehicle_context_suggestion) {
        setTimeout(async () => {
          try {
            const ragRes = await fetch(
              `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/diagnostics/vin-rag-brief`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  vehicle_context: data.vehicle_context_suggestion,
                  vin: trimmed,
                }),
              }
            );
            if (ragRes.ok) {
              const ragData = await ragRes.json();
              if (ragData.content) {
                setMessages((prev) => [
                  ...prev,
                  { role: 'bot', content: ragData.content },
                ]);
              }
            }
          } catch {
            // RAG bubble 2 failure is silent — bubble 1 already displayed
          }
        }, 900);
      }
    } catch {
      setVinError('VIN decode failed. Please try again.');
    } finally {
      setVinLoading(false);
    }
  };

  const isAnyLoading = loading || dtcLoading || vinLoading;

  return (
    <main className="flex h-screen w-full bg-background overflow-hidden transition-colors">

      {/* ── Sidebar ────────────────────────────────────────────── */}
      <div className="w-85 shrink-0 border-r border-[#a48fa3]/15 bg-card/50 flex flex-col h-full overflow-hidden transition-all duration-300">

        {/* Logo — fixed top */}
        <div className="shrink-0 px-8 pt-4 pb-3">
          <Card className="border-[#a48fa3]/50 bg-background/40 backdrop-blur-md shadow-sm rounded-[20px] overflow-hidden">
            <CardContent className="p-0">
              <img
                src={logoSrc}
                alt="Pojehat AI Logo"
                className="w-full h-auto object-contain"
              />
            </CardContent>
          </Card>
        </div>

        {/* Scrollable content area */}
        <div className="flex-1 min-h-0 overflow-y-auto px-8 pb-3 space-y-4">

          {/* Selected Vehicle */}
          <div className="space-y-2">
            <label
              className="text-[11px] font-black uppercase tracking-widest ml-2 flex items-center gap-1.5"
              style={{ color: '#a48fa3' }}
            >
              <Car size={10} />
              Selected Vehicle
            </label>
            <Input
              placeholder="e.g. Corolla 2020"
              value={vehicle}
              onChange={(e) => setVehicle(e.target.value)}
              className="bg-background border-[#a48fa3]/40 rounded-2xl h-10 text-sm placeholder:text-[12px]"
            />
          </div>

          {/* Error Code + VIN Decoder Panel */}
          <div className="space-y-2">
            <label
              className="text-[11px] font-black uppercase tracking-widest ml-2 flex items-center gap-1.5"
              style={{ color: '#a48fa3' }}
            >
              <AlertTriangle size={10} />
              Error Code
            </label>
            <Input
              placeholder="e.g. P0300, C1241, B1234"
              value={errorCode}
              onChange={(e) => setErrorCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); handleDtcSubmit(); }
              }}
              className="bg-background border-[#a48fa3]/40 rounded-2xl h-10 text-sm font-mono tracking-wider placeholder:text-[12px]"
            />
            <div className="px-4">
              <Button
                className="w-full h-9 text-sm font-extrabold rounded-[18px] shadow-md transition-all active:scale-[0.98] text-white mt-2"
                style={{ background: '#a48fa3' }}
                disabled={!errorCode.trim() || dtcLoading}
                onClick={handleDtcSubmit}
              >
                {dtcLoading ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-white/80 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                ) : (
                  <><AlertTriangle size={12} className="mr-1.5" />Submit Diagnostic</>
                )}
              </Button>
            </div>

            {/* ── VIN Decoder — directly below Submit Diagnostic ── */}
            <div className="pt-4">
              <div className="border-t-4 border-[#a48fa3]/30 mb-5" />
              <Input
                placeholder="Enter VIN (17 characters)"
                value={vin}
                onChange={(e) => { setVin(e.target.value.toUpperCase()); setVinError(''); }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !vinLoading) { e.preventDefault(); handleVinDecode(); } }}
                maxLength={17}
                disabled={vinLoading}
                className="bg-background border-[#a48fa3]/40 rounded-2xl h-10 text-sm font-mono tracking-wider placeholder:text-[12px]"
              />
              {vin.length > 0 && (
                <span className="text-[10px] text-muted-foreground ml-2 mt-1 block">
                  {vin.length}/17
                </span>
              )}
              {vinError && (
                <span className="text-[10px] text-red-500 ml-2 mt-1 block">{vinError}</span>
              )}
              <div className="px-4">
                <Button
                  className="w-full h-9 text-sm font-extrabold rounded-[18px] shadow-md transition-all active:scale-[0.98] text-white mt-4"
                  style={{ background: '#a48fa3' }}
                  disabled={vin.length !== 17 || vinLoading}
                  onClick={handleVinDecode}
                >
                  {vinLoading ? (
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 bg-white/80 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </span>
                  ) : (
                    <><Search size={12} className="mr-1.5" />Decode VIN</>
                  )}
                </Button>
              </div>
            </div>
          </div>

          {/* In-App Ingestion */}
          <div className="space-y-5">
            <ManualUpload />
            <div className="px-4">
              <Button
                onClick={handleKnowledgeAudit}
                disabled={isAnyLoading}
                className="w-full h-9 text-sm font-extrabold rounded-[18px] shadow-md transition-all active:scale-[0.98] text-white"
                style={{ background: '#a48fa3' }}
              >
                <ShieldCheck size={12} className="mr-1.5" />System Audit
              </Button>
            </div>
          </div>
        </div>

        {/* Footer — fixed bottom, visually separated — (Removed legacy bubbles) */}
        <div className="shrink-0 px-8 pb-5 pt-2">
        </div>
      </div>

      {/* ── Chat Area ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col relative bg-muted/20 min-h-0">
        <header className="h-[77px] border border-border/50 bg-card/50 backdrop-blur-xl flex items-center px-8 justify-between sticky top-4 mx-8 rounded-[40px] z-10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.1)] shrink-0">
          <div className="flex items-center gap-4">
            <div className="relative w-[180px] h-[50px] shrink-0 flex items-center justify-start ml-2">
              <img src={logoBanner.src} alt="Pojehat Logo" className="h-full w-auto object-contain object-left" />
            </div>
            <Badge variant="outline" className="bg-[#a48fa3]/10 text-[#a48fa3] border-[#a48fa3]/20 rounded-[20px] px-7 py-[14px] font-bold text-[10.5px] tracking-[0.05em] leading-tight max-w-[850px] text-center shadow-sm">
              Pojehat v1.3.2 - Tier III Diagnostics Agent | Error Code Panel - VIN Decoder - General Automotive Queries - Structured DTC Analysis & Reports
            </Badge>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <div className="h-4 w-px bg-border/50" />
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 rounded-full hover:text-[#a48fa3] border border-border/40"
              onClick={() => { setMessages([]); setVehicle(''); setErrorCode(''); setVin(''); setVinError(''); }}
              title="Reset Diagnostic Session"
            >
              <Wrench className="h-5 w-5" />
            </Button>
          </div>
        </header>

        <ScrollArea className="flex-1 min-h-0">
          <div className="max-w-3xl mx-auto space-y-5 p-8 pb-64">
            {messages.length === 0 && (
              <div className="text-center py-20 space-y-6">
                <div className="relative inline-block p-6 bg-card rounded-3xl border border-border shadow-2xl">
                  <img src={logoMain.src} alt="Pojehat AI" width="64" height="64" className="mx-auto" />
                  <div className="absolute -bottom-2 -right-2 bg-[#7f92a9] text-white p-1.5 rounded-full ring-4 ring-background">
                    <Wrench size={16} />
                  </div>
                </div>
                <div>
                  <h2 className="text-3xl font-extrabold tracking-tight text-foreground mb-4">Welcome to Pojehat</h2>
                  <p className="mt-3 text-muted-foreground max-w-sm mx-auto leading-relaxed">
                    Set your vehicle context, enter an error code in the side panel for a structured
                    diagnostic report, or chat below for any automotive question.
                  </p>
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 border shadow-sm relative overflow-hidden ${
                  m.role === 'user'
                    ? m.isDtc ? 'bg-[#a48fa3] border-[#a48fa3]' : 'bg-muted border-border'
                    : 'bg-white dark:bg-stone-900 border-border'
                }`}>
                  {m.role === 'user' ? (
                    m.isDtc
                      ? <AlertTriangle size={16} className="text-white" />
                      : <User size={18} className="text-muted-foreground" />
                  ) : (
                    <img src={logoMain.src} alt="P" className="w-full h-full object-contain p-1.5" />
                  )}
                </div>
                <Card className={`max-w-[90%] shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.15)] rounded-[32px] ${
                  m.role === 'user'
                    ? m.isDtc
                      ? 'bg-[#a48fa3]/15 border-[#a48fa3]/40 text-foreground'
                      : 'bg-[#a48fa3] text-white border-[#a48fa3]'
                    : 'bg-card border-border text-foreground'
                }`}>
                  <CardContent className="py-3 px-5 text-sm leading-relaxed">
                    {m.role === 'user' ? (
                      <div className={`whitespace-pre-wrap font-mono text-sm ${m.isDtc ? 'font-bold tracking-wide' : ''}`}>
                        {m.content}
                      </div>
                    ) : (
                      <div className="pojehat-prose max-w-none">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkBreaks]}
                          rehypePlugins={[rehypeRaw]}
                          components={{
                            table: ({ children }) => (
                              <div className="my-2 max-w-full overflow-hidden">
                                <table className="w-full border-collapse">{children}</table>
                              </div>
                            ),
                            p: ({ children }) => (
                              <p dir={isArabic(children) ? "rtl" : "auto"} className="mb-4 last:mb-0">
                                {children}
                              </p>
                            ),
                            ul: ({ children }) => (
                              <ul dir={isArabic(children) ? "rtl" : "ltr"} className="list-disc mb-4 space-y-1">
                                {children}
                              </ul>
                            ),
                            ol: ({ children }) => (
                              <ul dir={isArabic(children) ? "rtl" : "ltr"} className="list-decimal mb-4 space-y-1">
                                {children}
                              </ul>
                            ),
                            li: ({ children }) => (
                              <li 
                                dir={isArabic(children) ? "rtl" : "auto"} 
                                className={`mb-1 ${isArabic(children) ? 'text-right marker:text-right' : 'text-left'}`}
                              >
                                {children}
                              </li>
                            ),
                            h1: ({ children }) => <h1 dir="auto">{children}</h1>,
                            h2: ({ children }) => <h2 dir="auto">{children}</h2>,
                            h3: ({ children }) => <h3 dir="auto">{children}</h3>,
                            code: ({ className, children, ...props }) => {
                              const isBlock = className?.includes('language-');
                              if (isBlock) {
                                return <pre className="max-w-full overflow-x-auto"><code className={className} {...props}>{children}</code></pre>;
                              }
                              return <code className={className} {...props}>{children}</code>;
                            },
                          }}
                        >
                          {formatDiagnosticResponse(m.content)}
                        </ReactMarkdown>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            ))}
            {isAnyLoading && (
              <div className="flex gap-4">
                <div className="w-9 h-9 rounded-2xl bg-white dark:bg-stone-900 border border-border relative overflow-hidden animate-pulse shadow-sm">
                  <Image src="/pojehat-logo.png" alt="P" fill className="object-contain p-1.5 grayscale" />
                </div>
                <Card className="bg-card border-border shadow-sm rounded-2xl">
                  <CardContent className="p-4 flex gap-1.5 items-center">
                    <span className="w-1.5 h-1.5 bg-[#7f92a9]/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-[#7f92a9]/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-[#7f92a9]/80 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </CardContent>
                </Card>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Bar */}
        <div className="absolute bottom-0 left-0 right-0 p-8 pt-0 pointer-events-none">
          <div className="max-w-3xl mx-auto relative pointer-events-auto">
            <div className="absolute inset-0 bg-background/50 blur-3xl -z-10 h-32 -top-16 opacity-50" />
            <textarea
              placeholder="Ask any automotive question, describe a fault symptom, or chat about a vehicle issue..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
              }}
              className="w-full min-h-[85px] max-h-[220px] p-5 pt-[31px] pr-20 bg-card border rounded-[32px] shadow-[0_10px_40px_rgb(0,0,0,0.06)] resize-none text-sm leading-relaxed poj-textarea-accent transition-all placeholder:text-center placeholder:leading-[22px]"
            />
            <Button
              size="icon"
              className="absolute right-5 top-[42.5px] -translate-y-1/2 h-12 w-12 rounded-[22px] bg-[#a48fa3] hover:opacity-90 transition-all shadow-lg active:scale-95 disabled:grayscale disabled:opacity-50 text-white"
              onClick={handleSend}
              disabled={loading || !input.trim()}
            >
              <Send size={24} />
            </Button>
          </div>
          <p className="text-[10px] text-center text-[#a48fa3] mt-3 font-medium tracking-wide flex items-center justify-center gap-1.5 uppercase">
            <Wrench size={10} className="text-[#a48fa3]" />
            EMPOWERED BY J. SERVO LLC. | WWW.JSERVO.COM | HYBRID TECHNICAL KNOWLEDGE BASE
          </p>
        </div>
      </div>
    </main>
  );
}
