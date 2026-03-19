'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ingestFromWeb, uploadOEMManual } from '@/lib/api';
import { CheckCircle2, Globe, Loader2, UploadCloud } from 'lucide-react';
import { useState } from 'react';

export function ManualUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState<'file' | 'url'>('file');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleUpload = async () => {
    if (mode === 'file' && !file) return;
    if (mode === 'url' && !url) return;
    setLoading(true);
    setSuccess(false);
    try {
      if (mode === 'file' && file) {
        await uploadOEMManual(file, 'OEM Technical Manual');
      } else if (mode === 'url' && url) {
        await ingestFromWeb(url, 'OEM Technical Manual');
      }
      setSuccess(true);
      setFile(null);
      setUrl('');
    } catch (error) {
      console.error(error);
      alert(`Error during ${mode} ingestion. Check console.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-[#a48fa3]/30 bg-card shadow-sm rounded-[20px]">
      <CardHeader className="px-4 pt-2.5 pb-1">
        <CardTitle className="text-xs font-bold" style={{ color: '#a48fa3' }}>
          In-App Ingestion
        </CardTitle>
        <CardDescription className="text-[10px]">
          Add technical manuals to the hybrid library
        </CardDescription>
      </CardHeader>
      <CardContent className="px-4 pb-2.5 space-y-2.5">
        {/* Mode Toggle */}
        <div className="flex p-1 bg-muted rounded-[14px] gap-1 border border-border">
          <button
            onClick={() => setMode('file')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] font-bold rounded-[10px] transition-all ${
              mode === 'file'
                ? 'bg-background text-[#a48fa3] shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <UploadCloud size={11} /> File
          </button>
          <button
            onClick={() => setMode('url')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] font-bold rounded-[10px] transition-all ${
              mode === 'url'
                ? 'bg-background text-[#a48fa3] shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Globe size={11} /> URL
          </button>
        </div>

        {/* File or URL Input */}
        {mode === 'file' ? (
          <div className="space-y-1" key="file-input-group">
            <Label htmlFor="file" className="text-[10px] uppercase font-bold text-muted-foreground ml-1">
              PDF Schematic
            </Label>
            <Input
              id="file"
              key="file-input"
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="h-8 text-[10px] bg-muted/50 border-border cursor-pointer file:text-[#a48fa3] file:font-bold rounded-[12px]"
            />
          </div>
        ) : (
          <div className="space-y-1" key="url-input-group">
            <Label htmlFor="url" className="text-[10px] uppercase font-bold text-muted-foreground ml-1">
              Target URL
            </Label>
            <Input
              id="url"
              key="url-input"
              placeholder="https://manuals.co/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="h-8 text-xs bg-muted/50 border-border rounded-[12px] px-3 placeholder:text-[12px]"
            />
          </div>
        )}

        {/* Action Button */}
        <Button
          className="w-full h-9 text-sm bg-[#a48fa3] hover:opacity-90 font-bold rounded-[16px] shadow-sm transition-all active:scale-[0.98] text-white"
          disabled={(!file && mode === 'file') || (!url && mode === 'url') || loading}
          onClick={handleUpload}
        >
          {loading ? (
            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
          ) : mode === 'file' ? (
            <UploadCloud className="mr-2 h-3 w-3" />
          ) : (
            <Globe className="mr-2 h-3 w-3" />
          )}
          {loading ? 'Ingesting...' : mode === 'file' ? 'Upload' : 'Fetch'}
        </Button>

        {success && (
          <div className="flex items-center gap-2 text-[10px] text-green-600 dark:text-green-400 font-bold p-2 bg-green-500/10 rounded-lg border border-green-500/20 animate-in fade-in slide-in-from-top-1">
            <CheckCircle2 className="h-3 w-3" />
            Ingestion Pipeline Initialized
          </div>
        )}
      </CardContent>
    </Card>
  );
}
