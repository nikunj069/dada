# Project Context: BlackBox PS3 — Autonomous Embedded Firmware Testing & 3D Rig Instrument

This document summarizes the context, goals, and architectural implementation of the project built during this session. It serves as a historical record of our chat history and the solution developed for the hackathon.

## The Challenge
**Hackathon Problem Statement 3: AI Agent for Autonomous Embedded Firmware Testing**

Testing embedded firmware typically requires engineers to manually write test cases, set up hardware, run the firmware, and investigate failures. The goal of this challenge was to make firmware testing smarter and faster by building an AI agent capable of reading embedded firmware (C code), identifying edge cases, automatically generating tests, executing them in a virtual hardware environment (simulator), and analyzing the output to identify unexpected behavior.

## What We Built
We transformed a foundational demo repository into a **fully operational, real-data-backed instrument** with a highly polished, premium user interface (dubbed the "DARKINT" aesthetic).

### Core Features & Architecture
The system consists of three main pillars:

1. **The Autonomous AI Agent Pipeline (Python)**
   - **Firmware Analysis**: Uses Tree-sitter for AST parsing to deeply understand C firmware, extract function behaviors, and map logic paths (ignoring unneeded `#ifdef` blocks).
   - **Test Generation**: Automatically builds robust test scenarios targeting boundary conditions, state transitions, fault injections (e.g., sensor disconnection), and out-of-range inputs.
   - **Virtual Execution**: Executes the generated tests against a LabWired core silicon simulator.
   - **Evaluation**: Monitors GPIO states, UART logs, and sensor reads to detect inductive back-EMF glitches, threshold off-by-one errors, and unhandled hardware faults.

2. **The "DARKINT" Web Dashboard (HTML/Vanilla JS/CSS)**
   - A completely overhauled, visually exceptional frontend relying on PCB-copper framing, glassmorphism panels, phosphor glow badges, and dynamic micro-animations.
   - Features 7 distinct operational tabs:
     - **◉ 3D Hardware Rig**: An interactive Three.js PCB environment visualizing test telemetry (fan speeds, LED states, temperatures) in real-time.
     - **▦ Test Matrix**: A grid of all generated test scenarios, filtered by categories and verdicts.
     - **⬡ AST Behavior**: A side-by-side code viewer with syntax highlighting and a live behavior graph of function calls.
     - **⚠ Root Cause**: High-density AI diagnosis cards detailing exact lines of defective code and severity scores.
     - **◈ Runs Explorer**: A catalog of all trace runs, including a feature to do side-by-side 3D diffing of two different test runs.
     - **⬢ Boards**: Hardware descriptors mapping physical pins to the simulator.
     - **▤ Report**: A comprehensive, standalone HTML execution report.

3. **Interactive Firmware Upload (FastAPI Backend)**
   - The dashboard includes a "RUN AGENT" modal where users can paste their own custom C firmware code and select a target microprocessor (e.g., STM32F103).
   - Upon submission, the FastAPI backend (`web/server.py`) saves the code, dispatches the Autonomous Agent pipeline as a background task, and dynamically updates the UI via status polling.
   - Once complete, the frontend seamlessly fetches the new test results, traces, and AST data for the user's custom firmware without requiring a page reload.

## Development Journey Highlights
- **Migration to Real Data**: Transitioned the web UI from using mocked static JSON files to actively pulling real, generated telemetry and trace files (`artifacts/traces/`) via robust REST API endpoints.
- **UI/UX Polish**: Met strict user requirements for an "exceptional" design by implementing custom scrollbars, animated transport bars, live server clocks, and severity-colored defect cards.
- **End-to-End Loop**: Successfully closed the feedback loop by allowing dynamic user input to trigger the Python AI agent, verifying that the entire system works autonomously from code ingestion to 3D visualization.

---
*Built autonomously via AI Pair Programming.*
