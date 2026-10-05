# Security

Please report security problems privately through
[GitHub's private vulnerability reporting](https://github.com/moxart/tgju-rates/security/advisories/new)
rather than in a public issue.

What the program does that is worth knowing:

- It makes HTTPS requests to `www.tgju.org` and `call1.tgju.org` only.
- It writes only to its own files: the price history (`~/.local/share/tgju-rates/history.db`) and,
  when you create them, the settings and holdings files under `~/.config/tgju-rates/`.
- The holdings file contains what you own. It stays on your machine and is never sent anywhere.
- Desktop notifications run `notify-send` with the alert text as an argument, not through a shell.

Only the latest release gets fixes.
