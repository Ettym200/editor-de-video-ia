"use client";

import { useState, useRef } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LANGUAGES = [
  { value: "pt", label: "Português" },
  { value: "en", label: "Inglês" },
  { value: "it", label: "Italiano" },
  { value: "hu", label: "Húngaro" },
  { value: "es", label: "Espanhol" },
  { value: "de", label: "Alemão" },
];

const STYLES = [
  { value: "modern", label: "Moderno" },
  { value: "cinematic", label: "Cinematográfico" },
  { value: "minimal", label: "Minimalista" },
  { value: "energetic", label: "Energético" },
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
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold">Editor de Vídeo IA</h1>
          <p className="text-gray-400 mt-2">Envie seu vídeo cru e receba um vídeo editado profissionalmente</p>
        </div>

        {status === "idle" && (
          <div className="space-y-4">
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-gray-700 rounded-xl p-10 text-center cursor-pointer hover:border-violet-500 transition-colors"
            >
              {file ? (
                <p className="text-violet-400 font-medium">{file.name}</p>
              ) : (
                <>
                  <p className="text-gray-400">Clique para selecionar o vídeo</p>
                  <p className="text-gray-600 text-sm mt-1">MP4, MOV, AVI, MKV</p>
                </>
              )}
              <input ref={fileRef} type="file" accept="video/*" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)} />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">Idioma do vídeo</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white">
                {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">Estilo de edição</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white">
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>

            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={broll} onChange={(e) => setBroll(e.target.checked)}
                className="w-4 h-4 accent-violet-500" />
              <span className="text-gray-300">Adicionar b-roll automático (Pexels)</span>
            </label>

            <button onClick={handleUpload} disabled={!file}
              className="w-full bg-violet-600 hover:bg-violet-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-colors">
              Editar Vídeo
            </button>
          </div>
        )}

        {status === "uploading" && (
          <div className="text-center space-y-3">
            <div className="animate-spin w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full mx-auto" />
            <p className="text-gray-400">Enviando vídeo...</p>
          </div>
        )}

        {status === "processing" && jobStatus && (
          <div className="space-y-4">
            <div className="text-center">
              <div className="animate-spin w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full mx-auto" />
              <p className="text-gray-300 mt-3 font-medium">{jobStatus.message}</p>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-3">
              <div className="bg-violet-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${jobStatus.progress}%` }} />
            </div>
            <p className="text-center text-gray-500 text-sm">{jobStatus.progress}%</p>
          </div>
        )}

        {status === "completed" && jobId && (
          <div className="text-center space-y-4">
            <div className="text-5xl">✅</div>
            <p className="text-xl font-bold text-green-400">Vídeo pronto!</p>
            <a href={`${API_URL}/videos/${jobId}/download`} download
              className="inline-block bg-green-600 hover:bg-green-700 text-white font-semibold px-8 py-3 rounded-xl transition-colors">
              Baixar Vídeo
            </a>
            <button onClick={reset} className="block w-full text-gray-500 hover:text-gray-300 text-sm mt-2">
              Editar outro vídeo
            </button>
          </div>
        )}

        {status === "error" && (
          <div className="text-center space-y-4">
            <div className="text-5xl">❌</div>
            <p className="text-red-400">{error || "Erro ao processar vídeo"}</p>
            <button onClick={reset} className="bg-gray-800 hover:bg-gray-700 text-white px-6 py-2 rounded-lg">
              Tentar novamente
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
