"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { askMechanicAgent } from "@/lib/api";
import { ManualUpload } from "@/components/manual-upload";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import { Send, User, Wrench } from "lucide-react";

interface Message {
  role: "user" | "bot";
  content: string;
}

export default function PojehatDashboard() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !vehicle.trim()) return;

    const userMsg = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const result = await askMechanicAgent(userMsg, vehicle);
      setMessages((prev) => [...prev, { role: "bot", content: result.response }]);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [...prev, { role: "bot", content: "Error: Failed to connect to Pojehat engine." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex h-screen w-full bg-background overflow-hidden transition-colors">
      {/* Sidebar */}
      <div className="w-80 border-r border-border bg-card/50 p-6 flex flex-col gap-6 overflow-y-auto">
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 overflow-hidden rounded-2xl border border-border shadow-sm bg-white dark:bg-stone-900">
            <Image 
              src="/pojehat-logo.png" 
              alt="Pojehat Logo" 
              fill 
              className="object-contain p-1.5"
            />
          </div>
          <h1 className="text-xl font-bold tracking-tight">Pojehat<span className="text-teal-600 dark:text-teal-400">.AI</span></h1>
        </div>
        
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-muted-foreground uppercase">Selected Vehicle</label>
            <Input 
              placeholder="Set Context (e.g. Corolla 2020)" 
              value={vehicle}
              onChange={(e) => setVehicle(e.target.value)}
              className="bg-background border-border rounded-2xl h-11"
            />
          </div>
          <ManualUpload />
        </div>

        <div className="mt-auto p-4 bg-teal-500/10 rounded-[24px] border border-teal-500/20 backdrop-blur-sm shadow-sm">
          <p className="text-xs text-teal-700 dark:text-teal-300 font-bold">Tier-3 Diagnostic Agent</p>
          <p className="text-[10px] text-teal-600/80 dark:text-teal-400/80 mt-1">Ingest manuals to improve diagnostic accuracy.</p>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col relative bg-muted/20">
        <header className="h-16 border border-border/50 bg-card/50 backdrop-blur-xl flex items-center px-8 justify-between sticky top-4 mx-8 rounded-3xl z-10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.1)]">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20 rounded-full px-3">
              System Online
            </Badge>
            <span className="text-xs text-muted-foreground font-medium">v1.2.0-technical</span>
          </div>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <div className="h-4 w-px bg-border/50" />
            <Wrench className="h-5 w-5 text-muted-foreground hover:text-teal-500 transition-colors cursor-pointer" />
          </div>
        </header>

        <ScrollArea className="flex-1 p-8" customScrollRef={scrollRef}>
          <div className="max-w-3xl mx-auto space-y-6 pb-24">
            {messages.length === 0 && (
              <div className="text-center py-20 space-y-6">
                <div className="relative inline-block p-6 bg-card rounded-3xl border border-border shadow-2xl">
                  <Image 
                    src="/pojehat-logo.png" 
                    alt="Pojehat AI" 
                    width={64} 
                    height={64} 
                    className="mx-auto"
                  />
                  <div className="absolute -bottom-2 -right-2 bg-teal-600 text-white p-1.5 rounded-full ring-4 ring-background">
                    <Wrench size={16} />
                  </div>
                </div>
                <div>
                  <h2 className="text-3xl font-extrabold tracking-tight text-foreground">Welcome to Pojehat</h2>
                  <p className="mt-2 text-muted-foreground max-w-sm mx-auto leading-relaxed">
                    The ultimate Tier-3 Engineering Brain. Set your vehicle context and let&apos;s solve complex electrical diagnostics.
                  </p>
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-4 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 border shadow-sm relative overflow-hidden ${
                  m.role === "user" ? "bg-muted border-border" : "bg-white dark:bg-stone-900 border-border"
                }`}>
                  {m.role === "user" ? (
                    <User size={18} className="text-muted-foreground" />
                  ) : (
                    <Image src="/pojehat-logo.png" alt="P" fill className="object-contain p-1.5" />
                  )}
                </div>
                <Card className={`max-w-[85%] shadow-md rounded-[20px] ${
                  m.role === "user" 
                    ? "bg-teal-600 text-white border-teal-700" 
                    : "bg-card border-border text-foreground"
                }`}>
                  <CardContent className="p-4 text-sm leading-relaxed whitespace-pre-wrap">
                    {m.content}
                  </CardContent>
                </Card>
              </div>
            ))}
            {loading && (
              <div className="flex gap-4">
                <div className="w-9 h-9 rounded-2xl bg-white dark:bg-stone-900 border border-border relative overflow-hidden animate-pulse shadow-sm">
                  <Image src="/pojehat-logo.png" alt="P" fill className="object-contain p-1.5 grayscale" />
                </div>
                <Card className="bg-card border-border shadow-sm rounded-2xl">
                  <CardContent className="p-4 flex gap-1.5 items-center">
                    <span className="w-1.5 h-1.5 bg-teal-500/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-teal-500/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-teal-500/80 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input Bar */}
        <div className="absolute bottom-0 left-0 right-0 p-8 pt-0 pointer-events-none">
          <div className="max-w-3xl mx-auto relative pointer-events-auto">
            <div className="absolute inset-0 bg-background/50 blur-3xl -z-10 h-32 -top-16 opacity-50" />
            <textarea
              placeholder="Describe the diagnostic code or circuit failure..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              className="w-full min-h-[85px] max-h-[220px] p-5 pr-20 bg-card border border-border rounded-[32px] shadow-[0_10px_40px_rgb(0,0,0,0.06)] focus:ring-2 focus:ring-teal-500/50 focus:outline-none transition-all resize-none text-sm leading-relaxed"
            />
            <Button 
              size="icon"
              className="absolute right-5 bottom-5 h-12 w-12 rounded-[22px] bg-teal-600 hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600 transition-all shadow-lg active:scale-95 disabled:grayscale disabled:opacity-50"
              onClick={handleSend}
              disabled={loading || !input.trim() || !vehicle.trim()}
            >
              <Send size={24} />
            </Button>
          </div>
          <p className="text-[10px] text-center text-muted-foreground mt-3 font-medium tracking-wide flex items-center justify-center gap-1.5 uppercase">
            <Wrench size={10} className="text-teal-500" />
            Empowered by Tier-3 Technical Grounding • Hybrid Knowledge Search
          </p>
        </div>
      </div>
    </main>
  );
}
