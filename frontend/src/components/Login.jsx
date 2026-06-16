import React, { useState } from "react";
import { ArrowRight } from "lucide-react";
import { T, SANS, MONO } from "../tokens.js";
import { supabase } from "../supabase.js";

export default function Login() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setError(error.message);
    setLoading(false);
  };

  return (
    <div style={{ background: "#cfccc3", fontFamily: SANS, minHeight: "100vh" }}
      className="w-full flex items-center justify-center p-4">

      <div style={{ background: "#0e0f12", borderRadius: 44, padding: 11, boxShadow: "0 30px 70px -20px rgba(0,0,0,.55)" }}
        className="w-full">
        <div style={{ maxWidth: 392, margin: "0 auto" }}>
          <div style={{ background: T.canvas, borderRadius: 34 }}
            className="flex flex-col px-8 py-12">

            {/* Logo */}
            <div className="mb-10">
              <div className="flex items-center gap-2 mb-2">
                <div style={{ background: T.ink, color: T.canvas, fontFamily: MONO }}
                  className="w-8 h-8 rounded-xl flex items-center justify-center text-[17px] font-bold">⌁</div>
                <div style={{ color: T.ink, letterSpacing: 0.5 }} className="text-[18px] font-extrabold">СТОРИСКАСТ</div>
              </div>
              <p style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] tracking-widest uppercase">одна загрузка · все каналы</p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                required
                style={{ background: T.surface, border: `1.5px solid ${T.line}`, color: T.ink, fontFamily: SANS }}
                className="w-full rounded-2xl px-4 py-3.5 text-[14px] outline-none"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Пароль"
                required
                style={{ background: T.surface, border: `1.5px solid ${T.line}`, color: T.ink, fontFamily: SANS }}
                className="w-full rounded-2xl px-4 py-3.5 text-[14px] outline-none"
              />

              {error && (
                <p style={{ color: "#c0392b" }} className="text-[11px] text-center mt-1">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{ background: loading ? "#c9c6bd" : T.primary, color: loading ? "#8d8a82" : "#fff" }}
                className="w-full rounded-2xl py-3.5 font-bold text-[15px] flex items-center justify-center gap-2 mt-2 transition-colors"
              >
                {loading ? "Входим…" : "Войти"}
                {!loading && <ArrowRight size={18} />}
              </button>
            </form>

          </div>
        </div>
      </div>
    </div>
  );
}
