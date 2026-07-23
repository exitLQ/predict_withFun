# Security Policy

## Supported version

Security fixes are applied to the latest code on the `main` branch. Older
commits, forks, and third-party deployments are not maintained by this project.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting:

<https://github.com/exitLQ/predict_withFun/security/advisories/new>

Include only the information needed to reproduce and assess the issue:

- affected commit or deployed version;
- vulnerable route, component, or configuration;
- minimal reproduction steps;
- expected and observed security impact;
- suggested mitigation, if known.

Remove real API keys, passwords, cookies, DSNs, personal data, and unrelated
provider content. Use synthetic values in proof-of-concept material.

The project aims to acknowledge a report within three business days and
provide an initial assessment within fourteen days. These are targets, not a
guarantee. Please allow time for a coordinated fix before public disclosure.

## Scope

Relevant reports include authentication/authorization bypasses, session or
CSRF flaws, injection, secret exposure, unsafe proxy/header behavior, and
dependency vulnerabilities with a demonstrated project impact.

AI hallucinations, prediction disagreement, provider downtime, model quality,
and inaccurate market forecasts are product limitations rather than software
vulnerabilities unless they enable a concrete security boundary violation.
