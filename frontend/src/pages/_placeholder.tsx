import { CircleDashed } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
}

export function PlaceholderPage({ eyebrow, title, description }: PlaceholderPageProps) {
  return (
    <div className="space-y-8">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
          {eyebrow}
        </div>
        <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
          {title}
        </h1>
      </div>

      <Card className="grid place-items-center py-16">
        <CardContent className="flex flex-col items-center gap-4 text-center">
          <CircleDashed className="h-9 w-9 animate-pulse-glow text-hud-glow" />
          <p className="max-w-xl text-hud-textDim">{description}</p>
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
            Module reserved · Kernel build v1.1
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
