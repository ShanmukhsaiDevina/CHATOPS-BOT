# ChatOps Bot (DevOps Assistant)

## Overview
This project integrates a chatbot (Opsdroid) with GitHub Actions to fetch, analyze, and explain CI/CD logs. The bot assists DevOps teams by providing quick access to build and deployment information directly through chat commands.

## Current Progress (as of Oct 2025)
- Opsdroid successfully installed and configured locally via Docker.
- Skills modularized into `hello`, `logs`, and `explain`.
- `/hello` and `/logs` fully functional in Opsdroid Desktop.
- GitHub integration enabled with personal access token.
- Bot retrieves and displays last failed GitHub Action logs.

## Next Steps
- Improve `/explain` skill to analyze and summarize errors.
- Integrate LLM for contextual explanations.
- Add `/help` command and Slack connector.

## Project Structure
```
.
├── skills
│   ├── hello
│   ├── logs
│   └── explain
├── .github
│   └── workflows
├── Dockerfile
└── configuration.yaml
```

## How to Run Locally
Use the following Docker command to run the bot locally, supplying your GitHub credentials via environment variables:

```bash
docker run -e GITHUB_TOKEN=your_token -e GH_OWNER=your_github_owner -e GH_REPO=your_repo_name opsdroid-image
```
