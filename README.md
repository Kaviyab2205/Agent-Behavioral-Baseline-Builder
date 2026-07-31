# Agent Behavioral Baseline Builder

An AI-agent behavioral monitoring and governance system that establishes a behavioral baseline using synthetic scenarios and monitors production behavior for anomalies and long-term behavioral drift.

## Overview

AI agents can behave differently after deployment due to changes in prompts, models, tools, or production usage patterns. Without knowing what normal behavior looks like, it is difficult to identify abnormal activity.

The Agent Behavioral Baseline Builder solves this problem by first learning the normal behavior of an AI agent using synthetic test scenarios. It then compares production behavior against the established baseline and identifies abnormal behavior.

The system also detects behavioral drift over time and recommends creating a refreshed baseline when significant changes are detected.

---

## Key Features

- Agent registration and configuration
- System prompt and tool configuration
- Automatic generation of 50 synthetic scenarios
- Behavioral baseline creation
- Behavioral fingerprint generation
- Tool-call frequency analysis
- Average response length tracking
- Tool-call sequence analysis
- Data access pattern monitoring
- Intent distribution analysis
- Production behavior monitoring
- Anomaly scoring from 0–100
- Normal, Warning, and Alert classification
- Explainable anomaly detection
- Persistent anomaly event history
- Sliding-window behavioral drift detection
- Model/prompt update simulation
- Baseline refresh recommendation
- Baseline versioning and history
- Intent-based behavioral baselines
- Interactive Streamlit dashboard
- FastAPI backend
- SQLite persistent storage
- Automated testing with Pytest
- Swagger API documentation
- Docker support
- AWS deployment support using ECS/Fargate

---

## System Architecture

```text
                    AI Agent
                       |
                       v
             Agent Configuration
                       |
                       v
            Synthetic Scenario Generator
                       |
                       v
                 50 Scenarios
                       |
                       v
              Baseline Recorder
                       |
                       v
             Behavioral Fingerprint
                       |
                       v
                  Baseline v1
                       |
                       v
              Production Monitor
                       |
                       v
               Anomaly Scoring
                       |
          +------------+------------+
          |            |            |
          v            v            v
       NORMAL       WARNING       ALERT
          |            |            |
          +------------+------------+
                       |
                       v
              Drift Detection
                       |
                       v
             Baseline Refresh
                       |
                       v
                  Baseline v2