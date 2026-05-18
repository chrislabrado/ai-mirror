import { useEffect, useState } from "react";
import { ExternalLink, FileDown } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ExportGuide } from "@/types/api";

export function ExportGuidePage() {
  const [guide, setGuide] = useState<ExportGuide | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.exportGuide().then(setGuide).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
            Section 6.5 · Multi-Platform Extraction Manual
          </div>
          <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
            Export Guide
          </h1>
        </div>
        {guide && (
          <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3 text-right font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
            <div>Manifest</div>
            <div className="mt-1 text-hud-text">v{guide.version}</div>
            <div>{guide.last_updated}</div>
          </div>
        )}
      </div>

      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {guide && (
        <>
          <Card>
            <CardContent className="text-[15px] leading-relaxed text-hud-text">
              {guide.intro}
            </CardContent>
          </Card>

          <Card>
            <div className="px-7 pt-2">
              <Accordion type="multiple" className="w-full">
                {guide.platforms.map((p) => (
                  <AccordionItem key={p.slug} value={p.slug}>
                    <AccordionTrigger>
                      <span className="flex items-center gap-3">
                        <PlatformBadge slug={p.icon} />
                        <span>{p.name}</span>
                      </span>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="prose-hud space-y-3 pl-9">
                        <p>{p.summary}</p>

                        <ol className="ml-3 space-y-1.5">
                          {p.steps.map((s) => (
                            <li key={s.n} className="flex items-start gap-3">
                              <span className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border border-hud-glow/60 font-mono text-[10px] text-hud-glow">
                                {s.n}
                              </span>
                              <span className="text-hud-text">{s.text}</span>
                            </li>
                          ))}
                        </ol>

                        <div className="flex flex-wrap items-center gap-2 pt-2">
                          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textFaint">
                            Formats:
                          </span>
                          {p.output_formats.map((f) => (
                            <span
                              key={f}
                              className="rounded-sm border border-hud-glow/40 bg-hud-panel/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-hud-glow"
                            >
                              {f}
                            </span>
                          ))}
                        </div>

                        {p.notes.length > 0 && (
                          <ul className="space-y-1">
                            {p.notes.map((n, i) => (
                              <li key={i} className="text-hud-textDim">
                                {n}
                              </li>
                            ))}
                          </ul>
                        )}

                        {p.docs_url && (
                          <a
                            href={p.docs_url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.2em] text-hud-glow hover:underline"
                          >
                            Official docs <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
            <div className="border-t border-hud-line/60 px-7 py-4 font-mono text-[11px] uppercase tracking-[0.22em] text-hud-textFaint">
              <FileDown className="mr-2 inline h-3.5 w-3.5 text-hud-glow" />
              {guide.footer_note}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function PlatformBadge({ slug }: { slug: string }) {
  const letter = slug.slice(0, 1).toUpperCase();
  return (
    <span className="grid h-7 w-7 place-items-center rounded-sm border border-hud-glow/50 bg-hud-panel font-display text-[11px] text-hud-glow shadow-glowSoft">
      {letter}
    </span>
  );
}
