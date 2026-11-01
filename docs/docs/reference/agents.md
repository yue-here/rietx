# For agents

An agent that drives rietx reads the rietx skill, a protocol and a set of reference files in the agentskills.io format.

The protocol says what to free in what order, what to check before believing a number, and which numbers may be quoted.
An agent reads it whole before its first fit.
The reference files are lookups it loads when a task needs one, such as the API index, the diagnostic codes or a series of patterns.
[Calling rietx from a program](programs.md) gives the Python surface the skill drives: the exceptions, the answer types, an answer's JSON form and `capabilities()`.

## Installing the skill

The package carries the skill.
This command installs it into the current project:

```console
$ rietx skill --install .
```

The copy goes in `.agents/skills/rietx/`, which several harnesses read, and a link goes in each requested harness's own directory.
The command prints both paths, then two lines to add to the project's `AGENTS.md` or `CLAUDE.md`.
It does not write those lines itself.
`--agent NAME` adds a harness, and `rietx skill --list-agents` lists the ones it knows.
`--user` installs for your user account instead of one project.

## Reading the skill without installing it

`rietx skill --print` prints the protocol, and `rietx skill --print all` prints every file.
The same files are published at [rietx.org/skill/rietx/SKILL.md](https://rietx.org/skill/rietx/SKILL.md), one file at a time, for a harness that has network access and no install.
