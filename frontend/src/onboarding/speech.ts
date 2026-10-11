import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Speech into the answer box, through the browser's own recogniser — the Web
 * Speech API, English (India), where the browser has it. Where it does not,
 * `supported` is false and the screen shows no mic: a mic that does nothing
 * would be a lie.
 *
 * What is heard fills the box and is never sent on its own: speech gets
 * numbers wrong, and "five nine" or "72 kilo" matter. Chrome sends the audio
 * to Google to be read (spec/done/onboarding-goals.md § Rules and edge cases).
 */

/** The slice of the recogniser used here. lib.dom has its results, not it. */
interface Recogniser {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { results: SpeechRecognitionResultList }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

const Recogniser: (new () => Recogniser) | undefined = (() => {
  const w = window as unknown as {
    SpeechRecognition?: new () => Recogniser;
    webkitSpeechRecognition?: new () => Recogniser;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
})();

export function useSpeech(onHeard: (heard: string) => void) {
  const [listening, setListening] = useState(false);
  const live = useRef<Recogniser | null>(null);
  const heard = useRef(onHeard);
  heard.current = onHeard;

  const start = useCallback(() => {
    if (!Recogniser || live.current) return;
    const r = new Recogniser();
    r.lang = 'en-IN';
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    r.onresult = (e) => {
      let text = '';
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      heard.current(text.trim());
    };
    // An error ends the session too; `onend` follows it either way.
    r.onerror = () => undefined;
    r.onend = () => {
      if (live.current === r) live.current = null;
      setListening(false);
    };
    live.current = r;
    setListening(true);
    try {
      r.start();
    } catch {
      live.current = null;
      setListening(false);
    }
  }, []);

  /** Stop listening and keep what was heard. */
  const stop = useCallback(() => live.current?.stop(), []);

  /** Stop and drop anything still on its way — the answer is being sent. */
  const cancel = useCallback(() => {
    const r = live.current;
    if (!r) return;
    live.current = null;
    r.onresult = null;
    r.abort();
    setListening(false);
  }, []);

  useEffect(() => () => live.current?.abort(), []);

  return { supported: Boolean(Recogniser), listening, start, stop, cancel };
}
