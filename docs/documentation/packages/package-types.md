{% macro arg_table(args) -%}

Name | Description | Type | Required | Default
-----|-------------|------|----------|--------
{% for arg_name, arg in args.childs.items() %}{{ arg_name }} | {{ arg.doc.get_short_help() }} | {{ arg | get_arg_type_string }} | {{ "yes" if arg.required else "no" }} | {{ "" if not arg.default else arg.default }}
{% endfor %}
{%- endmacro %}

{% macro pkg_desc(pkg_name, expl) -%}

{% set pkg_data = expl.explanation_data %}
{% set doc = pkg_data["doc"] %}
{% set examples = pkg_data["examples"] %}
{% set args = pkg_data["args"] %}
{% set hide = doc.get_metadata_value("hide", False) %}
## type: **``{{ pkg_name }}``**

{{ doc.get_help('n/a') }}

### Args

{{ arg_table(args) }}

{% if examples %}
### Examples
{% for pkg_name, pkg in examples.items() %}

#### ``{{ pkg_name }}``

Package description:

```yaml
{{ {"source": pkg["source"]} | to_yaml }}
```
{% endfor %}
{% endif %}  
{%- endmacro %}

This page contains documentation and metadata for all package types that come with *bring*. The '*Args*' section in each item lists the argument each package type supports in the ``source`` part of a package description. For more details on how package descritions are build, check [here](/documentation/packages/package_description)

{% for pkg_name, expl in pkg_types.items() %}
{% if pkg_name != "folder" %}{{ pkg_desc(pkg_name, expl) }}{% endif %}
{% endfor %}
