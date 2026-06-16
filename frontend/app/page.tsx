"use client";

import { useState, useRef, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LANGUAGES = [
  { value: "pt", label: "🇧🇷 Português" },
  { value: "en", label: "🇺🇸 Inglês" },
  { value: "es", label: "🇪🇸 Espanhol" },
  { value: "it", label: "🇮🇹 Italiano" },
  { value: "de", label: "🇩🇪 Alemão" },
  { value: "hu", label: "🇭🇺 Húngaro" },
];

const STYLES = [
  { value: "modern", label: "Moderno", desc: "Clean, minimalista com acentos azuis", icon: "✨" },
  { value: "cinematic", label: "Cinematográfico", desc: "Tons dourados, dramático e elegante", icon: "🎬" },
  { value: "minimal", label: "Minimalista", desc: "Sutil, sem distrações", icon: "◻️" },
  { value: "energetic", label: "Energético", desc: "Cores vibrantes, impacto máximo", icon: "⚡" },
];

const STEPS = [
  { label: "Transcrevendo áudio", icon: "🎙️" },
  { label: "Removendo silêncios", icon: "✂️" },
  { label: "Buscando b-roll", icon: "🔍" },
  { label: "Aplicando efeitos", icon: "🎨" },
  { label: "Renderizando", icon: "🎞️" },
];

type Status = "idle" | "uploading" | "processing" | "completed" | "error";

interface JobStatus {
  status: string;
  progress: number;
  message: string;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("pt");
  const [style, setStyle] = useState("modern");
  const [broll, setBroll] = useState(true);
  const [status, setStatus] = useState<Status>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleFile = (f: File) => {
    if (f.type.startsWith("video/")) setFile(f);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    setError(null);

    const form = new FormData();
    form.append("file", file);
    form.append("language", language);
    form.append("style", style);
    form.append("broll", String(broll));

    try {
      const res = await fetch(`${API_URL}/videos/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error("Erro ao enviar vídeo");
      const data = await res.json();
      setJobId(data.job_id);
      setStatus("processing");
      pollStatus(data.job_id);
    } catch (e: unknown) {
      setStatus("error");
      setError(e instanceof Error ? e.message : "Erro desconhecido");
    }
  };

  const pollStatus = (id: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/jobs/${id}`);
        const data: JobStatus = await res.json();
        setJobStatus(data);
        if (data.status === "completed") {
          setStatus("completed");
          clearInterval(pollRef.current!);
        } else if (data.status === "error") {
          setStatus("error");
          setError(data.message);
          clearInterval(pollRef.current!);
        }
      } catch {}
    }, 2000);
  };

  const reset = () => {
    setFile(null);
    setStatus("idle");
    setJobId(null);
    setJobStatus(null);
    setError(null);
    if (pollRef.current) clearInterval(pollRef.current);
    if (fileRef.current) fileRef.current.value = "";
  };

  const activeStep = STEPS.findIndex((s) =>
    jobStatus?.message?.toLowerCase().includes(s.label.toLowerCase().split(" ")[0])
  );

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
      {/* Header */}
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-violet-600 flex items-center justify-center text-sm">🎬</div>
          <span className="font-semibold text-sm tracking-wide">VideoEdit IA</span>
        </div>
        <span className="text-xs text-white/30 bg-white/5 px-3 py-1 rounded-full">Beta</span>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl space-y-8">

          {/* Hero */}
          <div className="text-center space-y-3">
            <div className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs px-3 py-1 rounded-full">
              <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-pulse" />
              Powered by Claude AI + Whisper
            </div>
            <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-br from-white to-white/50 bg-clip-text text-transparent">
              Edição automática<br />com inteligência artificial
            </h1>
            <p className="text-white/40 text-sm max-w-sm mx-auto">
              Envie seu vídeo bruto e receba em minutos um vídeo editado com cortes, legendas e b-roll automáticos
            </p>
          </div>

          {/* Form */}
          {status === "idle" && (
            <div className="bg-white/[0.03] border border-white/8 rounded-2xl p-6 space-y-5">

              {/* Drop zone */}
              <div
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
                  ${dragging ? "border-violet-400 bg-violet-500/10" : "border-white/10 hover:border-violet-500/50 hover:bg-white/[0.02]"}
                  ${file ? "border-violet-500/50 bg-violet-500/5" : ""}`}
              >
                <input ref={fileRef} type="file" accept="video/*" className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />

                {file ? (
                  <div className="space-y-2">
                    <div className="text-3xl">🎥</div>
                    <p className="text-violet-300 font-medium text-sm">{file.name}</p>
                    <p className="text-white/30 text-xs">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                    <button onClick={(e) => { e.stopPropagation(); setFile(null); }}
                      className="text-xs text-white/30 hover:text-white/60 underline mt-1">
                      Trocar arquivo
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="text-3xl opacity-40">📁</div>
                    <p className="text-white/50 text-sm">Arraste seu vídeo aqui ou <span className="text-violet-400">clique para selecionar</span></p>
                    <p className="text-white/20 text-xs">MP4, MOV, AVI, MKV</p>
                  </div>
                )}
              </div>

              {/* Options grid */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs text-white/40 font-medium uppercase tracking-wider">Idioma</label>
                  <select value={language} onChange={(e) => setLanguage(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors">
                    {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs text-white/40 font-medium uppercase tracking-wider">Estilo</label>
                  <select value={style} onChange={(e) => setStyle(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors">
                    {STYLES.map((s) => <option key={s.value} value={s.value}>{s.icon} {s.label}</option>)}
                  </select>
                </div>
              </div>

              {/* Style preview */}
              {(() => {
                const s = STYLES.find(s => s.value === style);
                return s ? (
                  <p className="text-xs text-white/30 text-center">{s.icon} {s.desc}</p>
                ) : null;
              })()}

              {/* B-roll toggle */}
              <div
                onClick={() => setBroll(!broll)}
                className={`flex items-center justify-between p-4 rounded-xl border cursor-pointer transition-all
                  ${broll ? "border-violet-500/40 bg-violet-500/5" : "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]"}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">🎞️</span>
                  <div>
                    <p className="text-sm font-medium">B-roll automático</p>
                    <p className="text-xs text-white/30">Insere clipes e imagens relacionados ao conteúdo</p>
                  </div>
                </div>
                <div className={`w-10 h-5.5 rounded-full transition-colors relative flex-shrink-0
                  ${broll ? "bg-violet-600" : "bg-white/10"}`}
                  style={{ width: 40, height: 22 }}>
                  <div className={`absolute top-0.5 w-4.5 h-4.5 bg-white rounded-full shadow transition-transform
                    ${broll ? "translate-x-5" : "translate-x-0.5"}`}
                    style={{ width: 18, height: 18, top: 2, left: broll ? 20 : 2, position: "absolute", transition: "left 0.2s" }} />
                </div>
              </div>

              {/* Submit */}
              <button onClick={handleUpload} disabled={!file}
                className="w-full bg-violet-600 hover:bg-violet-500 disabled:bg-white/5 disabled:text-white/20 disabled:cursor-not-allowed
                  text-white font-semibold py-3.5 rounded-xl transition-all duration-200 text-sm
                  shadow-lg shadow-violet-600/20 hover:shadow-violet-500/30">
                {file ? "✨ Editar vídeo com IA" : "Selecione um vídeo para começar"}
              </button>
            </div>
          )}

          {/* Uploading */}
          {status === "uploading" && (
            <div className="bg-white/[0.03] border border-white/8 rounded-2xl p-10 text-center space-y-4">
              <div className="w-12 h-12 border-2 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-white/60 text-sm">Enviando vídeo...</p>
            </div>
          )}

          {/* Processing */}
          {status === "processing" && (
            <div className="bg-white/[0.03] border border-white/8 rounded-2xl p-8 space-y-8">
              <div className="text-center space-y-2">
                <div className="w-12 h-12 border-2 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-white font-medium">{jobStatus?.message || "Processando..."}</p>
                <p className="text-white/30 text-xs">Isso pode levar alguns minutos dependendo do tamanho do vídeo</p>
              </div>

              {/* Progress bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-white/30">
                  <span>Progresso</span>
                  <span>{jobStatus?.progress || 0}%</span>
                </div>
                <div className="w-full bg-white/5 rounded-full h-1.5">
                  <div className="bg-gradient-to-r from-violet-600 to-violet-400 h-1.5 rounded-full transition-all duration-700"
                    style={{ width: `${jobStatus?.progress || 0}%` }} />
                </div>
              </div>

              {/* Steps */}
              <div className="grid grid-cols-5 gap-2">
                {STEPS.map((step, i) => {
                  const progress = jobStatus?.progress || 0;
                  const stepProgress = (i + 1) * 20;
                  const done = progress >= stepProgress;
                  const current = progress >= stepProgress - 20 && progress < stepProgress;
                  return (
                    <div key={i} className={`text-center space-y-1.5 transition-all
                      ${done ? "opacity-100" : current ? "opacity-80" : "opacity-25"}`}>
                      <div className={`text-xl transition-transform ${current ? "animate-bounce" : ""}`}>
                        {done ? "✅" : step.icon}
                      </div>
                      <p className="text-[10px] text-white/50 leading-tight">{step.label}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Completed */}
          {status === "completed" && jobId && (
            <div className="bg-white/[0.03] border border-white/8 rounded-2xl p-10 text-center space-y-6">
              <div className="space-y-2">
                <div className="text-5xl">🎉</div>
                <h2 className="text-xl font-bold text-white">Vídeo pronto!</h2>
                <p className="text-white/40 text-sm">Seu vídeo foi editado com sucesso pela IA</p>
              </div>
              <div className="space-y-3">
                <a href={`${API_URL}/videos/${jobId}/download`} download
                  className="flex items-center justify-center gap-2 w-full bg-green-600 hover:bg-green-500 text-white font-semibold py-3.5 rounded-xl transition-colors shadow-lg shadow-green-600/20">
                  ⬇️ Baixar vídeo editado
                </a>
                <button onClick={reset}
                  className="w-full text-white/30 hover:text-white/60 text-sm py-2 transition-colors">
                  Editar outro vídeo
                </button>
              </div>
            </div>
          )}

          {/* Error */}
          {status === "error" && (
            <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-8 text-center space-y-4">
              <div className="text-4xl">⚠️</div>
              <p className="text-red-400 text-sm">{error || "Erro ao processar vídeo"}</p>
              <button onClick={reset}
                className="bg-white/5 hover:bg-white/10 text-white px-6 py-2.5 rounded-lg text-sm transition-colors">
                Tentar novamente
              </button>
            </div>
          )}

          {/* Footer */}
          <p className="text-center text-white/15 text-xs">
            Powered by Claude AI · Whisper · FFmpeg · Pexels
          </p>
        </div>
      </div>
    </main>
  );
}
