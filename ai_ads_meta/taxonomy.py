"""Rule-based coding of records: relevance, ad format, effect on users, method, framing.

The patterns are transparent heuristics over title + abstract. They are meant
for screening and descriptive mapping; codes used in a paper should be
spot-checked by hand.
"""

from __future__ import annotations

import re

from .model import Record


def _rx(*alts: str) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.I)


AI_TERMS = _rx(
    r"large language models?", r"LLMs?", r"generative (?:ai|artificial intelligence|models?)",
    r"gen-?ai", r"chat-?bots?", r"conversational (?:ai|agents?|assistants?|systems?)",
    r"chatgpt", r"gpt-?\d\w*", r"neural networks?", r"deep learning", r"ai[- ]generated",
    r"artificial intelligence", r"recommender systems?", r"(?:voice|virtual|ai) assistants?",
    r"ai (?:agents?|systems?|models?)", r"language models?", r"algorithm(?:s|ic)?",
)

AD_TERMS = _rx(
    r"advertis\w+", r"ads?", r"sponsor\w+", r"marketing", r"promot(?:ion|ional|ed)\w*",
    r"product placements?", r"commercial (?:content|messages?|interests?)",
    r"brand(?:s|ed|ing)?", r"moneti[sz]\w+",
)

TAXONOMY: dict[str, dict[str, re.Pattern]] = {
    "ad_format": {
        "conversational_ads": _rx(
            r"sponsored (?:answers?|responses?|content|results?|recommendations?)",
            r"ads? (?:in|within|inside) (?:chat-?bots?|conversations?|llms?|responses?|answers?)",
            r"native advertis\w+", r"(?:chat-?bot|conversational|llm) advertis\w+",
            r"advertis\w+ in (?:large language models?|llms?|chat-?bots?|conversational)",
            r"product placements?",
        ),
        "ai_generated_creative": _rx(
            r"ai[- ]generated (?:ads?|advertis\w+|content|images?|videos?|copy)",
            r"ad(?:vertising)? (?:copy|creatives?|text) generation",
            r"(?:virtual|ai|synthetic) influencers?", r"deepfakes?",
            r"generat\w+ (?:of )?(?:ads?|advertis\w+)",
        ),
        "targeting_personalization": _rx(
            r"personali[sz]ed (?:ads?|advertis\w+|marketing|recommendations?|content)",
            r"targeted (?:ads?|advertis\w+)", r"behaviou?ral advertis\w+",
            r"micro-?target\w+", r"programmatic", r"ad targeting", r"personali[sz]ation",
        ),
        "recommendation_bias": _rx(
            r"product recommendations?", r"recommender systems?",
            r"brand (?:bias|preferences?|mentions?|visibility)",
            r"generative engine optimi[sz]ation", r"search engines?", r"ranking",
        ),
        "disclosure_labeling": _rx(
            r"disclos\w+", r"label(?:s|ing|ed|ling|led)?", r"transparen\w+", r"watermark\w*",
        ),
        "covert_dark_patterns": _rx(
            r"dark patterns?", r"covert\w*", r"stealth\w*", r"hidden", r"undisclosed",
            r"decepti\w+", r"subliminal",
        ),
    },
    "user_effect": {
        "trust_credibility": _rx(r"trust\w*", r"distrust\w*", r"credib\w+", r"skeptic\w+"),
        "manipulation_persuasion": _rx(
            r"manipulat\w+", r"persua\w+", r"nudg\w+", r"decepti\w+", r"mislead\w+", r"exploit\w+",
        ),
        "privacy": _rx(
            r"privacy", r"surveillance", r"data protection", r"personal data", r"tracking", r"profiling",
        ),
        "purchase_behavior": _rx(
            r"purchase (?:intent\w*|decisions?|behaviou?r)", r"buying", r"consumer behaviou?r",
            r"willingness to pay", r"click-?through", r"conversion", r"(?:brand|ad) attitudes?",
        ),
        "autonomy_agency": _rx(
            r"autonom\w+", r"agency", r"free will", r"choice architecture", r"decision[- ]making",
        ),
        "wellbeing": _rx(
            r"well-?being", r"addict\w+", r"anxiety", r"mental health", r"loneliness",
            r"dependen(?:ce|cy)", r"emotional\w*",
        ),
        "fairness_vulnerable_groups": _rx(
            r"discriminat\w+", r"fairness", r"stereotyp\w+", r"vulnerab\w+", r"children",
            r"minors", r"adolescents?", r"elderly",
        ),
        "satisfaction_engagement": _rx(
            r"satisfaction", r"engagement", r"user experience", r"usability",
            r"perceived usefulness", r"acceptance",
        ),
        "misinformation": _rx(
            r"misinformation", r"disinformation", r"hallucinat\w+", r"false claims?", r"fake",
        ),
        "social_norms_anomie": _rx(
            r"anomi[ea]\w*", r"normless\w*", r"alienation", r"social norms?", r"norm (?:erosion|violation)",
            r"societal (?:harms?|impact|consequences?)",
        ),
    },
    "method": {
        "experiment": _rx(
            r"experiment\w*", r"randomi[sz]ed", r"a/b test\w*", r"between-subjects?", r"within-subjects?",
        ),
        "survey": _rx(r"surveys?", r"questionnaires?", r"structural equation", r"pls-sem", r"respondents"),
        "qualitative": _rx(r"interviews?", r"focus groups?", r"qualitative", r"thematic analysis"),
        "system_audit": _rx(
            r"audit\w*", r"benchmark\w*", r"red[- ]team\w*", r"prompt injection",
            r"we (?:evaluate|test|probe)", r"dataset",
        ),
        "review": _rx(
            r"(?:literature|systematic|scoping|narrative) review", r"meta-analy\w+", r"bibliometric\w*",
        ),
        "conceptual_legal": _rx(
            r"conceptual", r"theoretical framework", r"regulat\w+", r"legal", r"law", r"policy",
            r"gdpr", r"digital services act", r"ai act", r"governance",
        ),
    },
}

RISK_CUES = _rx(
    r"risks?", r"harm\w*", r"manipulat\w+", r"decepti\w+", r"mislead\w+", r"distrust\w*", r"erod\w+",
    r"erosion", r"threat\w*", r"concerns?", r"exploit\w+", r"undermin\w+", r"backlash",
    r"reduc\w+ (?:trust|credibility)", r"negative(?:ly)?",
)
BENEFIT_CUES = _rx(
    r"benefits?", r"improv\w+", r"enhanc\w+", r"effective(?:ness)?", r"increas\w+ (?:engagement|trust|sales)",
    r"helpful", r"opportunit\w+", r"positive(?:ly)?", r"efficien\w+",
)

DIMENSIONS = list(TAXONOMY)


def feature_names() -> list[str]:
    return [f"{dim}:{cat}" for dim in DIMENSIONS for cat in TAXONOMY[dim]]


def classify(r: Record) -> Record:
    """Fill relevance, taxonomy codes and framing on a record (in place)."""
    text = f"{r.title}. {r.abstract}"
    ai_t, ad_t = len(AI_TERMS.findall(r.title)), len(AD_TERMS.findall(r.title))
    ai_a, ad_a = len(AI_TERMS.findall(r.abstract)), len(AD_TERMS.findall(r.abstract))
    # relevant = the record talks about both AI and advertising
    r.relevant = (ai_t + ai_a) > 0 and (ad_t + ad_a) > 0
    r.relevance = (2 * (ai_t + ad_t) + min(ai_a, 5) + min(ad_a, 5)) if r.relevant else 0
    for dim in DIMENSIONS:
        setattr(r, dim, [cat for cat, rx in TAXONOMY[dim].items() if rx.search(text)])
    risk, benefit = len(RISK_CUES.findall(text)), len(BENEFIT_CUES.findall(text))
    if risk == 0 and benefit == 0:
        r.framing = "neutral"
    elif risk >= 2 * benefit:
        r.framing = "risk"
    elif benefit >= 2 * risk:
        r.framing = "benefit"
    else:
        r.framing = "mixed"
    return r
