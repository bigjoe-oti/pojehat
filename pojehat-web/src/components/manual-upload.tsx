"use client";

import { useState } from "react";
import { uploadOEMManual, ingestFromWeb } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Loader2, UploadCloud, CheckCircle2, Globe } from "lucide-react";

export function ManualUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"file" | "url">("file");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleUpload = async () => {
    if (!context) return;
    if (mode === "file" && !file) return;
    if (mode === "url" && !url) return;

    setLoading(true);
    setSuccess(false);
    try {
      if (mode === "file" && file) {
        await uploadOEMManual(file, context);
      } else if (mode === "url" && url) {
        await ingestFromWeb(url, context);
      }
      setSuccess(true);
      setFile(null);
      setUrl("");
      setContext("");
    } catch (error) {
      console.error(error);
      alert(`Error during ${mode} ingestion. Check console.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="h-full border-border bg-card shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-bold">In-App Ingestion</CardTitle>
        <CardDescription className="text-[10px]">Add technical manuals to the hybrid library</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex p-1 bg-muted rounded-[18px] gap-1 border border-border">
          <button 
            onClick={() => setMode("file")}
            className={`flex-1 flex items-center justify-center gap-2 py-1.5 text-[10px] font-bold rounded-[14px] transition-all ${
              mode === "file" ? "bg-background text-teal-600 dark:text-teal-400 shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <UploadCloud size={12} />
            File
          </button>
          <button 
            onClick={() => setMode("url")}
            className={`flex-1 flex items-center justify-center gap-2 py-1.5 text-[10px] font-bold rounded-[14px] transition-all ${
              mode === "url" ? "bg-background text-teal-600 dark:text-teal-400 shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Globe size={12} />
            URL
          </button>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="vehicle" className="text-[10px] uppercase font-bold text-muted-foreground">Vehicle Identity</Label>
          <Input 
            id="vehicle" 
            placeholder="e.g. Mazda 3 2019" 
            value={context}
            onChange={(e) => setContext(e.target.value)}
            className="h-9 text-xs bg-muted/50 border-border rounded-xl px-3"
          />
        </div>

        {mode === "file" ? (
          <div className="space-y-1.5" key="file-input-group">
            <Label htmlFor="file" className="text-[10px] uppercase font-bold text-muted-foreground">PDF Schematic</Label>
            <Input 
              id="file" 
              key="file-input"
              type="file" 
              accept=".pdf" 
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="h-9 text-[10px] bg-muted/50 border-border cursor-pointer file:text-teal-600 dark:file:text-teal-400 file:font-bold rounded-xl"
            />
          </div>
        ) : (
          <div className="space-y-1.5" key="url-input-group">
            <Label htmlFor="url" className="text-[10px] uppercase font-bold text-muted-foreground">Target URL</Label>
            <Input 
              id="url" 
              key="url-input"
              placeholder="https://manuals.co/..." 
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="h-9 text-xs bg-muted/50 border-border rounded-xl px-3"
            />
          </div>
        )}

        <Button 
          className="w-full h-10 text-xs bg-teal-600 hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600 font-bold rounded-xl shadow-md transition-all active:scale-[0.98]" 
          disabled={(!file && mode === "file") || (!url && mode === "url") || !context || loading}
          onClick={handleUpload}
        >
          {loading ? (
            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
          ) : mode === "file" ? (
            <UploadCloud className="mr-2 h-3 w-3" />
          ) : (
            <Globe className="mr-2 h-3 w-3" />
          )}
          {loading ? "Ingesting..." : mode === "file" ? "Upload" : "Fetch"}
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
