import type { PaperAnalysis } from '@/types/strategist';

const KNOWN_DATASETS = [
    'imagenet',
    'cifar-10',
    'cifar10',
    'cifar-100',
    'cifar100',
    'coco',
    'mnist',
    'fashion-mnist',
    'wikitext',
    'squad',
    'librispeech',
    'msrvtt',
    'kitti',
];

function compactWhitespace(text: string): string {
    return text.replace(/\s+/g, ' ').trim();
}

function firstNonTrivialLine(lines: string[]): string {
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.length < 8 || trimmed.length > 180) continue;
        if (/^(\d+|page \d+|arxiv:|https?:\/\/)/i.test(trimmed)) continue;
        return trimmed;
    }
    return 'Research Paper';
}

function toSentenceSummary(text: string, maxSentences: number): string {
    const cleaned = compactWhitespace(text);
    const sentences = cleaned
        .split(/(?<=[.!?])\s+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 20);
    return (sentences.slice(0, maxSentences).join(' ') || cleaned.slice(0, 500)).trim();
}

function inferDomain(text: string): PaperAnalysis['domain'] {
    const lower = text.toLowerCase();
    if (/(image|vision|segmentation|detection|clip|diffusion|vit|cnn)/.test(lower)) return 'cv';
    if (/(language|text|llm|transformer|token|nlp|bert|gpt)/.test(lower)) return 'nlp';
    if (/(robot|control|manipulation|locomotion|policy learning)/.test(lower)) return 'robotics';
    if (/(training|optimization|gradient|loss|benchmark|generalization)/.test(lower)) return 'ml';
    return 'other';
}

function extractDatasetNames(text: string): { name: string; size: string; source: string }[] {
    const lower = text.toLowerCase();
    const found = KNOWN_DATASETS
        .filter((name) => lower.includes(name))
        .slice(0, 4)
        .map((name) => ({
            name: name.toUpperCase().replace('-10', '10').replace('-100', '100'),
            size: 'N/A',
            source: 'paper text',
        }));
    return found;
}

function extractEquations(rawText: string): { latex: string; description: string; section: string }[] {
    const matches = rawText
        .split('\n')
        .map((line) => line.trim())
        .filter((line) =>
            line.length > 6 &&
            line.length < 160 &&
            line.includes('=') &&
            !line.toLowerCase().includes('http') &&
            /[a-zA-Z]/.test(line)
        )
        .slice(0, 3);

    return matches.map((latex, idx) => ({
        latex,
        description: `Equation extracted from paper text (${idx + 1})`,
        section: 'paper',
    }));
}

function extractMetricRows(text: string): { name: string; value: string; comparison: string }[] {
    const rows: { name: string; value: string; comparison: string }[] = [];
    const lower = text.toLowerCase();
    const patterns: Array<{ name: string; regex: RegExp }> = [
        { name: 'Accuracy', regex: /accuracy[^0-9]{0,20}([0-9]{1,3}(?:\.[0-9]+)?%)/i },
        { name: 'F1', regex: /f1[^0-9]{0,20}([0-9]{1,3}(?:\.[0-9]+)?)/i },
        { name: 'BLEU', regex: /bleu[^0-9]{0,20}([0-9]{1,3}(?:\.[0-9]+)?)/i },
        { name: 'ROUGE', regex: /rouge[^0-9]{0,20}([0-9]{1,3}(?:\.[0-9]+)?)/i },
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern.regex);
        if (match?.[1]) {
            rows.push({
                name: pattern.name,
                value: match[1],
                comparison: 'Extracted from paper text',
            });
        } else if (lower.includes(pattern.name.toLowerCase())) {
            rows.push({
                name: pattern.name,
                value: 'N/A',
                comparison: 'Mentioned in paper',
            });
        }
    }
    return rows.slice(0, 4);
}

function extractAbstract(rawText: string, title: string): string {
    const text = compactWhitespace(rawText);
    const lower = text.toLowerCase();
    const abstractIdx = lower.indexOf('abstract');
    if (abstractIdx >= 0) {
        const start = abstractIdx + 'abstract'.length;
        const introIdx = lower.indexOf('introduction', start);
        const end = introIdx > start ? introIdx : Math.min(start + 1800, text.length);
        return toSentenceSummary(text.slice(start, end), 3);
    }

    const trimmed = text.startsWith(title) ? text.slice(title.length).trim() : text;
    return toSentenceSummary(trimmed.slice(0, 1800), 3);
}

function extractClaims(abstractSummary: string): string[] {
    const candidates = abstractSummary
        .split(/(?<=[.!?])\s+/)
        .map((s) => s.trim())
        .filter((s) =>
            /we (propose|present|show|introduce|demonstrate|evaluate)|our method|results show|outperform/i.test(s)
        );

    if (candidates.length > 0) {
        return candidates.slice(0, 4);
    }

    if (abstractSummary.length > 0) {
        return [abstractSummary];
    }

    return ['Core claims could not be extracted automatically from the uploaded text.'];
}

function extractLimitations(rawText: string): string[] {
    const text = compactWhitespace(rawText);
    const lower = text.toLowerCase();
    const idx = lower.search(/limitations?|future work|discussion/);
    if (idx >= 0) {
        const snippet = text.slice(idx, idx + 600);
        const summary = toSentenceSummary(snippet, 2);
        return summary ? [summary] : ['Limitations section is present in the paper.'];
    }
    return ['Detailed limitations were not explicitly extracted in fallback mode.'];
}

export function buildFallbackPaperAnalysis(paperContext: string): PaperAnalysis {
    const lines = paperContext
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    const title = firstNonTrivialLine(lines);
    const abstractSummary = extractAbstract(paperContext, title);
    const keyClaims = extractClaims(abstractSummary);
    const contributions = keyClaims.slice(0, 3);
    const limitations = extractLimitations(paperContext);

    return {
        title,
        authors: [],
        abstract_summary: abstractSummary,
        equations: extractEquations(paperContext),
        model_architecture: null,
        datasets: extractDatasetNames(paperContext),
        metrics: extractMetricRows(paperContext),
        key_claims: keyClaims,
        contributions,
        limitations,
        domain: inferDomain(paperContext),
        hallucination_risk: {
            level: 'medium',
            reasons: ['Fallback parser used because primary model call failed.'],
        },
    };
}
