# ``githbub-release``

todo...

```yaml
source:
  type: github-release
  user_name: <github_user_or_org>
  repo_name: <repo_name>
  artefact_name: <optional_artefact_name>
  url_regex:
    - 'https://github.com/markelog/eclectica/releases/download/v(?P<version>.*)/ec_(?P<os>.*)_(?P<arch>.*)$'
```

``artefact_name`` is only necessary when several packages use the same repo for different files
``url_regex`` is a list of regexes, of which the first one that matches items will be used. Usually, only one is necessary.
