---
title: "Agent Skills for Ethnographic Analysis"
tags: 
- anthropology
- ethnography
- research
- LLMagent
- en
- DOI
- install
categories: 
date: 2026-11-07
lastMod: 2026-11-07
abstract: "A catalogue of agent skills for anthropologists"
---
**Version 0.1 – a working catalogue**

These are agent skills and tools I use and develop around ethnographic analysis: finding literature, organising research materials, following digital fieldsites, and creating novel analytic perspectives. They support the work anthropological work around interpretation. Some of them have more general scientific uses too.

The skills are split into two categories: deterministic and heuristic. Deterministic skills can be used by both humans and AI harnesses with identical results. Heuristic skills require either AI inference or human judgement. So, "agent" here means any entity with tool-using and inferential capabilities.

All of the tools listed here are in private use in my own research workflows, at different stages of development and testing. **litreview and ScholarFocus are already publicly available as experimental releases.** The remaining entries are previews: I will release them once they have been tested enough and their documentation and configuration are ready for use beyond my own setup. There is no release timetable yet.

Here, a *skill* means instructions an agent can follow, often accompanied by scripts. Some entries are broader workflows. For example, Researchwall is currently a standalone script, and I'm not yet sure if this useful (to me) experiment makes sense to publish as a reusable package.

## Published skills

### litreview – finding anthropological literature

**Question:** What has been written about this topic, and which conversations should I follow?

litreview searches OpenAlex, follows citations forwards and backwards, and assembles an evidence base for a literature review. It takes a research question or topic, optionally seeded with known works, and produces ranked references and a thematic outline or a structured screening summary. The retrieval runs in code; an agent can then use the results to draft a review.

It is tuned with anthropological research in mind, including **monographs, edited volumes and their chapters**, rather than being journal-centric. An optional local JSTOR metadata index supplements citation-database discovery with books and chapters, and links chapters to their parent volumes. This is particularly useful for work that is easy to miss in article-centred searches.

**Example request:** “Map the anthropological literature on maintenance and repair. Include books and chapters in edited volumes where available, distinguish the main conversations, and tell me where coverage is thin.”

Main use for this skill is discovery and review preparation. Screening uses titles, abstracts and metadata, not full texts. Citation links and database classifications have gaps. The output should not be presented as a comprehensive or PRISMA-compliant review.

+ [Skill instructions and supporting files](https://github.com/wilenius/scholarfocus-skill/tree/main/skills/litreview).

+ Skill type: deterministic (but upstream sources use machine learning classification)

### ScholarFocus – situating researchers and their work

**Question:** What does this researcher work on, who do they collaborate with, and what do they cite?

ScholarFocus takes a name or, preferably, an ORCID identifier. It uses OpenAlex and ORCID to assemble a profile of publications, research topics, co-authors and frequently cited works. Multiple researchers can be compared to find shared references and collaborations: useful starting points for exploring intellectual connections.

**Example request:** “Using these two ORCID identifiers, compare the researchers’ publications, collaborators and shared references. Flag uncertain matches and gaps.”

A bibliographic profile is not an account of someone’s intellectual life. For example, name ambiguity, merged author records and uneven indexing can distort it. ORCID helps with identification but does not eliminate missing material. Treat the profile as a guide for further reading.

+ [Skill instructions and supporting files](https://github.com/wilenius/scholarfocus-skill/tree/main/skills/scholarfocus).

+ Skill type: deterministic (but upstream sources use machine classification)

### Getting the skills

Both skills live in one [GitHub repository under wilenius](https://github.com/wilenius/scholarfocus-skill), because they share the same `scholarlib` command-line package. The repository includes a Claude Code marketplace/plugin; other compatible agents can use the individual skill directories. The command-line package and the skill files are installed separately: see the [installation instructions](https://github.com/wilenius/scholarfocus-skill#install).

Future releases will be grouped by shared code and dependencies, rather than creating a repository for every instruction file. The catalogue here will link to each release.

## In private use (releases forthcoming)

+ **Researchwall – an analytical workspace.** Combines Logseq notes, Zotero references, research folders and participant metadata into a zoomable wall and printable sheets. Links between materials remain visible, and changed sheets can be reprinted individually. Currently a project-specific script; a public release needs a generic configuration and a synthetic example wall, not my research data. Let me know if you're interested in testing it!

+ **Logseq / Zettelkasten.** Block-aware retrieval, linked analytical notes and note-ID maintenance: infrastructure for revisiting observations and developing connections without losing their sources.

+ **Zotero and literature search.** Semantic, keyword and tag searches; reconciliation of library and web results; reference import and deduplication. These complement litreview by working closely with an existing personal library. This is based on [zotero-mcp](https://github.com/54yyyu/zotero-mcp).

+ **Feed triage and deep reading.** A Matcha-based workflow that selects relevant feed items, saves references and nominates papers for reading. Full-text reading produces analytical Zotero notes; triage from a title or abstract is kept separate from claims about the paper’s findings.

+ **Digital fieldsite monitoring.** GitHub activity summaries and Jira issue retrieval help follow software development over time. They identify events and discussions to investigate, rather than treating repository activity as self-explanatory evidence of work practices.

+ **Reflexive journalling and synthesis.** Experimental agent-generated accounts of human–agent collaboration, revisited alongside research notes and literature.

+ **Influence Mapper.** Connects public data from multiple sources to map institutional relationships.

## Why these tools?

The aim is to make research materials easier to find and to make connections across research data while leaving interpretation to the researcher. A central design principle is that retrieval results, generated suggestions and researcher’s claims should remain distinguishable, with routes back to their sources.

For the wider setup, see [Tools of the trade]({{< ref "/pages/Tools of the trade" >}}) and [The three maxims of synthesised ethnography]({{< ref "/pages/The three maxims of synthesised ethnography" >}}). This page will grow as individual tools become ready to share.

