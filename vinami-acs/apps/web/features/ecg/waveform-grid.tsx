import type { ECGWaveformView } from "@web/entities/ecg/model";

const WIDTH = 360;
const HEIGHT = 108;
const PADDING = 12;

export function WaveformGrid({ value }: { value: ECGWaveformView }) {
  return (
    <div className="vm-ecg-waveform-grid" aria-label="Twelve-lead ECG waveform">
      {value.leads.map((lead) => (
        <figure className="vm-ecg-lead" key={lead.name}>
          <figcaption>{lead.name}</figcaption>
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label={`${lead.name} waveform`}
            preserveAspectRatio="none"
          >
            <path className="vm-ecg-grid-minor" d={gridPath(18, 18)} />
            <path className="vm-ecg-grid-major" d={gridPath(90, 54)} />
            <path className="vm-ecg-trace" d={waveformPath(lead.samples)} />
          </svg>
        </figure>
      ))}
    </div>
  );
}

function waveformPath(samples: number[]): string {
  if (samples.length < 2) return "";
  const visible = downsample(samples, 320);
  const maximum = Math.max(...visible.map((sample) => Math.abs(sample)), 1);
  return visible
    .map((sample, index) => {
      const x =
        PADDING + (index / (visible.length - 1)) * (WIDTH - PADDING * 2);
      const y = HEIGHT / 2 - (sample / maximum) * (HEIGHT * 0.36);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function downsample(samples: number[], limit: number): number[] {
  if (samples.length <= limit) return samples;
  const step = samples.length / limit;
  return Array.from(
    { length: limit },
    (_, index) => samples[Math.floor(index * step)] ?? 0,
  );
}

function gridPath(horizontal: number, vertical: number): string {
  const segments: string[] = [];
  for (let x = 0; x <= WIDTH; x += horizontal)
    segments.push(`M${x} 0V${HEIGHT}`);
  for (let y = 0; y <= HEIGHT; y += vertical) segments.push(`M0 ${y}H${WIDTH}`);
  return segments.join(" ");
}
