# Changelog fragments

Each pull request adds its `CHANGELOG_v2.md` entry as a new file in this
directory instead of editing `CHANGELOG_v2.md`. A new file never conflicts
with another pull request, so merging `develop/v2` into a branch no longer
needs a changelog conflict resolved. At release, `towncrier` collects the
files into `CHANGELOG_v2.md` and deletes them.

## Add an entry

1. Create `changelog.d/<issue>.<type>.md`, for example `740.fixed.md`.
   - `<type>` is one of the types in `[tool.towncrier]` in `pyproject.toml`.
   - For a second entry for the same issue and type, add a counter:
     `740.fixed.1.md`.
   - For a change without an issue, start the name with `+`:
     `+ci-cache.changed.md`.
2. Write the entry as you would have written the bullet in `CHANGELOG_v2.md`,
   without the leading `- `. Put the issue reference, such as `(#740)`, in the
   text yourself; nothing is appended to it. Markdown paragraphs, lists, code
   spans and tables are kept as written.

## Preview

```bash
uvx towncrier@26.9.0 build --draft --version Unreleased
```

The command prints the section that the release would add and changes no
file. It fails on a file name whose type is unknown, which towncrier would
otherwise drop without a message. CI runs the same command on every pull
request.

## Release (maintainers)

```bash
uvx towncrier@26.9.0 build --version <version> --date <YYYY-MM-DD>
```

This inserts `## <version> — <date>` below the
`<!-- towncrier release notes start -->` marker in `CHANGELOG_v2.md` and
removes the fragments with `git rm`. The `## Unreleased` section written
before this directory existed is not a fragment: at the first release, move
its entries into the new version section by hand, then delete the empty
`## Unreleased` heading.
