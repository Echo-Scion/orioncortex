import os
import shutil
import argparse
import re
import json
import sys
import subprocess

def _log_telemetry(err: Exception, context: str = "") -> None:
    """Non-fatal telemetry catch for degraded operations."""
    if os.environ.get("ORION_DEBUG"):
        msg = f": {err}" if err else ""
        sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")


if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


AI_CONFIGS = {
    "gemini": {"template": "AGENTS.template.md", "target_dir": "", "target_path": "GEMINI.md", "format": "md"},
    "copilot": {"template": "AGENTS.template.md", "target_dir": ".github", "target_path": "copilot-instructions.md", "format": "md"},
    "cursor": {"template": "AGENTS.template.md", "target_dir": "", "target_path": ".cursorrules", "format": "md"},
    "windsurf": {"template": "AGENTS.template.md", "target_dir": "", "target_path": ".windsurfrules", "format": "md"},
    "cline": {"template": "AGENTS.template.md", "target_dir": "", "target_path": ".clinerules", "format": "md"},
    "claude": {"template": "AGENTS.template.md", "target_dir": "", "target_path": "CLAUDE.md", "format": "md"},
    "agents": {"template": "AGENTS.template.md", "target_dir": "", "target_path": "AGENTS.md", "format": "md"}
}

def get_ecosystem_config(foundation_dir, framework):
    if not framework:
        return {}
    eco_json_path = os.path.join(foundation_dir, ".agents", "canons", "ecosystems", framework.lower(), "ecosystem.json")
    if not os.path.exists(eco_json_path):
        eco_json_path = os.path.join(foundation_dir, "canons", "ecosystems", framework.lower(), "ecosystem.json")
    if os.path.exists(eco_json_path):
        try:
            with open(eco_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as _e:
            _log_telemetry(_e, 'foundation.py:37')
    return {}

def detect_stack(target_dir):
    """
    Auto-detect framework and language from target project markers.
    """
    if os.path.exists(os.path.join(target_dir, "pubspec.yaml")):
        return "flutter", "dart"
    if os.path.exists(os.path.join(target_dir, "package.json")):
        try:
            with open(os.path.join(target_dir, "package.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "next" in deps or "react" in deps:
                    is_ts = os.path.exists(os.path.join(target_dir, "tsconfig.json"))
                    return "react", "typescript" if is_ts else "javascript"
        except Exception as _e:
            _log_telemetry(_e, 'foundation.py:55')
        is_ts = os.path.exists(os.path.join(target_dir, "tsconfig.json"))
        return "node", "typescript" if is_ts else "javascript"
    if os.path.exists(os.path.join(target_dir, "pyproject.toml")) or os.path.exists(os.path.join(target_dir, "requirements.txt")):
        return "python", "python"
    if os.path.exists(os.path.join(target_dir, "Cargo.toml")):
        return "rust", "rust"
    if os.path.exists(os.path.join(target_dir, "go.mod")):
        return "go", "go"
    return "generic", "generic"

def get_stack_defaults(framework, language):
    fw_lower = (framework or "generic").lower()
    lang_lower = (language or "generic").lower()
    if fw_lower == "flutter" or lang_lower == "dart":
        return {
            "FRAMEWORK": "flutter",
            "LANGUAGE": "dart",
            "STATE_MANAGEMENT": "riverpod",
            "MODEL_TYPE": "Freezed",
            "tech_stack": "Dart/Flutter, Python, SQLite",
            "primary_languages": "Dart, Python",
            "frontend_framework": "Flutter",
            "backend_persistence": "Supabase / SQLite",
            "state_management_choice": "Riverpod 2.x",
            "arch_framework": "Flutter",
            "state_management": "Riverpod",
            "ui_framework": "Flutter Material 3",
            "ui_kit_reference": "Tailwind / Flutter Material 3",
        }
    if fw_lower in ["react", "next"] or (fw_lower == "node" and lang_lower in ["typescript", "javascript"]):
        return {
            "FRAMEWORK": fw_lower,
            "LANGUAGE": lang_lower if lang_lower != "generic" else "typescript",
            "STATE_MANAGEMENT": "zustand",
            "MODEL_TYPE": "zod",
            "tech_stack": f"{lang_lower.capitalize()}, {fw_lower.capitalize()}, Node.js",
            "primary_languages": lang_lower.capitalize(),
            "frontend_framework": fw_lower.capitalize(),
            "backend_persistence": "Postgres / Prisma / SQLite",
            "state_management_choice": "Zustand",
            "arch_framework": f"{fw_lower.capitalize()} Clean Architecture",
            "state_management": "Zustand",
            "ui_framework": "Tailwind CSS / Radix UI",
            "ui_kit_reference": "Tailwind CSS / shadcn/ui",
        }
    if fw_lower == "python" or lang_lower == "python":
        return {
            "FRAMEWORK": "fastapi" if fw_lower == "generic" else fw_lower,
            "LANGUAGE": "python",
            "STATE_MANAGEMENT": "pydantic",
            "MODEL_TYPE": "pydantic",
            "tech_stack": "Python, SQLite / Postgres",
            "primary_languages": "Python",
            "frontend_framework": "FastAPI / Standard UI",
            "backend_persistence": "SQLAlchemy / SQLite",
            "state_management_choice": "Pydantic Models",
            "arch_framework": "Clean Python Architecture",
            "state_management": "Pydantic Models",
            "ui_framework": "HTML/Tailwind",
            "ui_kit_reference": "Tailwind CSS",
        }
    return {
        "FRAMEWORK": fw_lower,
        "LANGUAGE": lang_lower,
        "STATE_MANAGEMENT": "modular",
        "MODEL_TYPE": "typed_models",
        "tech_stack": "Modular Architecture",
        "primary_languages": lang_lower.capitalize(),
        "frontend_framework": "Modular UI",
        "backend_persistence": "Persistent Storage",
        "state_management_choice": "Predictable State",
        "arch_framework": "Feature-First Clean Architecture",
        "state_management": "Unidirectional State Flow",
        "ui_framework": "Standard UI Kit",
        "ui_kit_reference": "Standard Design System",
    }

TEMPLATE_VARS = {
    "FRAMEWORK": "generic",
    "LANGUAGE": "generic",
    "STATE_MANAGEMENT": "modular",
    "CLI_TEST_COVERAGE": "80%",
    "MODEL_TYPE": "standard",
    "LLM_TIER": "cloud_agent",
    "date": "2026-10-05",
    "timestamp": "2026-10-05T00:00:00Z",
    "timezone": "UTC",
    "current_phase": "Phase 1: Architecture & Design",
    "category_name": "Core",
    "domain_overview": "Domain architecture and strategic objectives.",
    "strategic_insights": "High leverage opportunities and market position.",
    "data_points": "Primary business and technical metrics.",
    "next_actions": "Complete MVP scope and technical verification.",
    "tagline": "Intelligent, autonomous agentic workspace.",
    "core_problem": "Friction and fragmentation in developer workflows.",
    "primary_persona": "Full-stack and mobile engineers.",
    "value_proposition": "Autonomous, verified development workflows.",
    "node_identifier": "foundation-core",
    "etymology": "Core structural baseline.",
    "trinity_keywords": "Autonomy, Verification, Performance",
    "core_intent": "Build rock-solid software systems.",
    "relationship_to_mission": "Foundational architecture layer.",
    "big_claim": "High-fidelity agentic engineering.",
    "dual_lens_concept": "Tactical execution paired with strategic reflection.",
    "first_30_seconds": "Immediate context awareness and zero-friction startup.",
    "retention_strategy": "Self-healing verification gates.",
    "fragmentation_risk": "Isolated sub-modules with divergent conventions.",
    "scale_limitations": "Context window limits and token latency.",
    "security_notes": "Zero hardcoded secrets, strict input validation.",
    "competitor_gap": "Lack of mechanical verification and self-evolving knowledge.",
    "unfair_advantage": "Portable brain graph and deterministic execution loops.",
    "mvp_scope": "End-to-end verification, deterministic routing, and zero data loss.",
    "peak_scope": "Autonomous evolution, multi-agent mesh, and predictive synthesis.",
    "proactive_feature_recommendations": "Continuous background verification and automatic linting.",
    "scalability_roadmap": "Modular expansion into cross-platform spokes.",
    "tech_stack": "Universal Stack",
    "visual_aesthetic": "Modern Bento UI with Spatial Glassmorphism",
    "visual_aesthetic_keywords": "clean, tactile, modern, glassmorphic",
    "database_schema_detail": "Relational/Document storage with integrity checks",
    "shared_services_mapping": "Orion Ops, Heartbeat Monitor, Telemetry Logger",
    "data_flow_hooks": "Pre/Post tool execution hooks",
    "sovereignty_notes": "Local-first execution with zero third-party lock-in",
    "saas_startup_mapping": "Lean 4-Pillar hierarchy",
    "context_mapping_summary": "Strategy, Product, Creative, Tech",
    "structural_pillars_checklist": "8 structural pillars satisfied",
    "primary_languages": "Polyglot",
    "frontend_framework": "Universal UI",
    "backend_persistence": "Database / API Storage",
    "hosting_provider": "Self-hosted / Cloud",
    "folder_architecture_pattern": "Feature-First Clean Architecture",
    "state_management_choice": "Predictable State Management",
    "api_contract_type": "REST / Realtime Channels",
    "auth_strategy": "Standard Auth Strategy",
    "performance_focus": "High throughput and low latency",
    "ci_cd_provider": "GitHub Actions",
    "testing_philosophy": "Strict Test-Driven Development (TDD)",
    "user_name": "Engineer",
    "user_role": "Architect",
    "tier": "Standard",
    "task_id": "INIT-001",
    "task_name": "Project Initialization",
    "priority": "High",
    "top_lessons": "Verify exit codes mechanically.",
    "arch_framework": "Modular Architecture",
    "state_management": "Unidirectional State Flow",
    "database": "Database",
    "ui_framework": "Standard UI",
    "layout_approach": "Responsive Grid & Flexbox",
    "brand_voice": "Technical, precise, confident",
    "primary_palette": "Deep Indigo, Slate Neutral, Cyan Accent",
    "typography_stack": "Inter, Roboto Mono",
    "ui_kit_reference": "Standard Design System",
    "north_star_metric": "Weekly Active Productive Hours",
    "anti_goals": "No slow blocking UI calls, no monolithic single files",
    "out_of_scope_list": "Legacy migrations outside active scope",
    "phase_1_goal": "Foundational architecture and core models",
    "phase_1_timeline": "Sprint 1",
    "phase_2_goal": "Feature implementation and state wiring",
    "phase_2_timeline": "Sprint 2",
    "phase_3_goal": "End-to-end testing and production release",
    "idea_category_summary": "Core concepts and problem discovery.",
    "validation_category_summary": "Customer feedback and demand testing.",
    "planning_category_summary": "Product roadmap and feature priorities.",
    "design_category_summary": "Visual system and component tokens.",
    "development_category_summary": "Application logic and system implementation.",
    "infrastructure_category_summary": "Hosting, storage, and deployment pipelines.",
    "testing_category_summary": "Unit, integration, and security verification.",
    "launch_category_summary": "Release milestones and distribution channels.",
    "acquisition_category_summary": "User discovery and outreach strategies.",
    "distribution_category_summary": "Marketplaces, communities, and partnerships.",
    "conversion_category_summary": "Onboarding and user journey optimization.",
    "revenue_category_summary": "Pricing models and monetization mechanics.",
    "analytics_category_summary": "Metrics, events, and performance tracking.",
    "retention_category_summary": "Engagement loops and churn prevention.",
    "growth_category_summary": "Viral mechanics and referral programs.",
    "scaling_category_summary": "System automation and capacity scaling.",
    "decision_1_title": "Adopt Feature-First Riverpod Architecture",
    "decision_1_logic": "Isolates feature domains and enables concurrent development.",
    "decision_1_tradeoffs": "Slight initial boilerplate in exchange for testability.",
    "topic_1": "State Management Lifecycle",
    "knowledge_1": "AutoDispose providers require explicit watch or keepAlive to maintain cache.",
    "friction_pattern_description": "Manual template variable substitution across fresh spokes.",
    "proposed_automation_fix": "Comprehensive TEMPLATE_VARS substitution engine in foundation.py.",
    "feature_1": "Authentication",
    "feature_2": "Core Dashboard",
    "feature_3": "Data Sync Engine",
    "feature_4": "Audit Verifier",
    "feature_5": "Telemetry Logger",
    "feature_6": "Offline Cache",
    "metric_1": "App startup latency < 1.5s",
    "metric_2": "Zero unhandled exceptions",
    "next_step_1": "Run full test suite",
    "next_step_2": "Deploy to staging",
    "issue_id": "DEBT-001",
    "description": "Clean up unused imports",
    "completed_feature_1": "Project scaffolding",
    "slots": "template slots",
    "x": "example-value"
}

def resolve_templates(target_dir, manifest, target_files=None):
    framework = manifest.get("framework") or TEMPLATE_VARS.get("FRAMEWORK")
    language = manifest.get("language") or TEMPLATE_VARS.get("LANGUAGE")
    
    if target_files is None:
        target_files = []
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".md"):
                    target_files.append(os.path.join(root, file))
    else:
        target_files = [os.path.join(target_dir, f) for f in target_files]
        
    for filepath in target_files:
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            new_content = content
            project_name = os.path.basename(os.path.abspath(target_dir))
            new_content = new_content.replace("{project_name}", project_name).replace("{{PROJECT_NAME}}", project_name)

            if framework:
                new_content = new_content.replace("{{FRAMEWORK}}", framework)
            if language:
                new_content = new_content.replace("{{LANGUAGE}}", language)
                
            # Derive package file & ecosystem tools
            fw_lower = (framework or "flutter").lower()
            lang_lower = (language or "dart").lower()
            if fw_lower == "flutter" or lang_lower == "dart":
                pkg_file, pkg_mgr, test_cmd = "pubspec.yaml", "flutter pub", "flutter test"
            elif fw_lower in ["react", "next", "node"] or lang_lower in ["javascript", "typescript"]:
                pkg_file, pkg_mgr, test_cmd = "package.json", "npm", "npm test"
            elif lang_lower == "python":
                pkg_file, pkg_mgr, test_cmd = "requirements.txt", "pip", "pytest"
            elif lang_lower == "rust":
                pkg_file, pkg_mgr, test_cmd = "Cargo.toml", "cargo", "cargo test"
            else:
                pkg_file, pkg_mgr, test_cmd = "package.json", "npm", "npm test"

            new_content = new_content.replace("{{PACKAGE_FILE}}", pkg_file)
            new_content = new_content.replace("{{PACKAGE_MANAGER}}", pkg_mgr)
            new_content = new_content.replace("{{TEST_RUNNER}}", test_cmd)
                
            llm_profile = manifest.get("llm_profile", {})
            if llm_profile:
                new_content = new_content.replace("{{LLM_TIER}}", llm_profile.get("intelligence_tier", "cloud_agent"))

            # Substitute remaining TEMPLATE_VARS (skip template definition directory to preserve templates)
            norm_path = filepath.replace('\\', '/')
            is_template_definition = "/templates/" in norm_path or norm_path.endswith("/templates")
            if not is_template_definition:
                for var_key, default_val in TEMPLATE_VARS.items():
                    placeholder_curly = "{{" + var_key + "}}"
                    if placeholder_curly in new_content:
                        val = manifest.get(var_key) or default_val
                        new_content = new_content.replace(placeholder_curly, str(val))
                
            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
        except Exception as e:
            print(f"    [WARNING] Failed to resolve templates in {filepath}: {e}")

def get_foundation_path(target_root):
    marker = os.path.join(target_root, ".agents", ".foundation_path")
    if os.path.exists(marker):
        with open(marker, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def load_deployed_ais(target_root):
    marker = os.path.join(target_root, ".agents", ".deployed_ais")
    if os.path.exists(marker):
        try:
            with open(marker, "r", encoding="utf-8") as f:
                return json.load(f).get("deployed_ais", [])
        except Exception as _e:
            _log_telemetry(_e, 'foundation.py:337')
    return None

def smart_merge_config(template_content, target_path, project_name, fmt, dry_run, manifest):
    content = template_content.replace("{project_name}", project_name)
    if manifest:
        for var_key, default_val in TEMPLATE_VARS.items():
            placeholder_curly = "{{" + var_key + "}}"
            if placeholder_curly in content:
                val = manifest.get(var_key) or default_val
                content = content.replace(placeholder_curly, str(val))
    
    merge_status = "Deployed (Fresh)"
    
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            old_content = f.read()
            
        if not dry_run:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            shutil.copy2(target_path, target_path + "." + ts + ".bak")
            
        marker = "<!-- END FOUNDATION MANDATES -->"
        idx = old_content.find(marker)
        if idx != -1:
            user_content = old_content[idx + len(marker):].strip()
            idx_new = content.find(marker)
            if idx_new != -1:
                base_new = content[:idx_new + len(marker)]
                content = base_new + "\n\n" + user_content + "\n"
                merge_status = "Merged (Preserved user config)"
            else:
                content += "\n\n" + user_content + "\n"
                merge_status = "Merged (Preserved user config, marker missing in template)"
        else:
            # Marker not found, preserve the entire old config to avoid data loss
            content += "\n\n" + old_content + "\n"
            merge_status = "Merged (Appended missing marker config)"

    if not dry_run:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
    return content, merge_status

# Folders that represent "The Brain" and should evolve
EVOLVABLE_FOLDERS = ["skills", "rules", "canons", "templates", "scripts", "evals", "docs", "hooks"]
ROOT_SYNC_FILES = ["DEPLOY_ME.md", "AGENTS_INDEX.md", "hooks.json"]
SEED_FILES = [
    "context/00_Strategy/BLUEPRINT.md",
    "context/00_Strategy/MEMORY.md",
    "context/01_Product/ROADMAP.md",
    "context/02_Creative/STYLE_GUIDE.md",
    "context/03_Tech/ARCHITECTURE.md",
    "context/AGENT_IDENTITY.md",
    "context/README.md"
]
VERSION_BUMP_FILES = {"SKILL.md"}
BLACKLIST = {
    "local", "tasks", "personal", "debug_scripts",
    "pull_planning_context.py", ".git", "node_modules",
    "__pycache__", "vitals", "MEMORY.md", "SAAS_MEMORY.md",
    "EVOLUTION_LOG.jsonl", ".project_manifest.json",
    ".foundation_path", ".deployed_ais", ".genome.json"
}

# === DEPLOY ===


def cmd_deploy(args):
    # args.target, args.framework, args.language, args.dry_run
    target_dir = os.path.abspath(args.target)
    foundation_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    target_agents_dir = os.path.join(target_dir, ".agents")
    
    # Auto-detect framework & language if omitted
    framework = args.framework
    language = args.language
    if not framework or not language:
        det_fw, det_lang = detect_stack(target_dir)
        framework = framework or det_fw
        language = language or det_lang
        print(f"  -> Stack Auto-Detected: framework='{framework}', language='{language}'")
    
    if args.dry_run:
        print(f"[DRY RUN] Deploying Foundation to: {target_dir}")
        print(f"[DRY RUN] Framework: {framework}, Language: {language}")
    else:
        print(f"Deploying Foundation to: {target_dir}")
        print(f"Framework: {framework}, Language: {language}")

    os.makedirs(target_agents_dir, exist_ok=True)
    
    manifest_path = os.path.join(target_agents_dir, ".project_manifest.json")
    llm_tier = "cloud_agent"
    if args.use_local_llm or args.llm_params > 0:
        if args.llm_params >= 30:
            llm_tier = "high_intelligence"
        elif args.llm_params >= 8:
            llm_tier = "medium_intelligence"
        elif args.llm_params > 0:
            llm_tier = "low_intelligence"
        else:
            llm_tier = "unknown_local"

    stack_vars = get_stack_defaults(framework, language)
    manifest = {
        "framework": framework,
        "language": language,
        "ecosystem": get_ecosystem_config(foundation_dir, framework),
        "llm_profile": {
            "is_local": args.use_local_llm or args.llm_params > 0,
            "parameters_b": args.llm_params,
            "intelligence_tier": llm_tier
        },
        **stack_vars
    }
    
    print(f"  -> LLM Profile: {llm_tier} (Local: {args.use_local_llm}, Params: {args.llm_params}B)")
    
    if not args.dry_run:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  -> Created {manifest_path}")
        
        genome_path = os.path.join(target_agents_dir, ".genome.json")
        with open(genome_path, "w", encoding="utf-8") as f:
            json.dump({"evolution_count": 0, "daily_mutation_cap": 10}, f, indent=2)
    else:
        print(f"  [SIMULATED] -> Created {manifest_path} with ecosystem variables")

    marker_path = os.path.join(target_agents_dir, ".foundation_path")
    if not args.dry_run:
        with open(marker_path, "w", encoding="utf-8") as f:
            f.write(foundation_dir)
        print(f"  -> Created {marker_path}")
    else:
        print(f"  [SIMULATED] -> Created {marker_path}")

    for folder in EVOLVABLE_FOLDERS:
        src = os.path.join(foundation_dir, ".agents", folder)
        dest = os.path.join(target_agents_dir, folder)
        if os.path.exists(src):
            if not args.dry_run:
                shutil.copytree(src, dest, dirs_exist_ok=True)
                resolve_templates(dest, manifest)
            else:
                print(f"  [SIMULATED] -> Copied & Resolved Templates for {folder}/")

    for root_file in ROOT_SYNC_FILES:
        src_root = os.path.join(foundation_dir, ".agents", root_file)
        dest_root = os.path.join(target_agents_dir, root_file)
        if os.path.exists(src_root):
            if not args.dry_run:
                shutil.copy2(src_root, dest_root)
            else:
                print(f"  [SIMULATED] -> Copied {root_file}")

    for seed_file in SEED_FILES:
        src_seed = os.path.join(foundation_dir, seed_file)
        if seed_file.startswith(".agents/"):
            dest_seed = os.path.join(target_agents_dir, seed_file.replace(".agents/", ""))
        else:
            dest_seed = os.path.join(target_dir, seed_file)
            
        if os.path.exists(src_seed):
            if not os.path.exists(dest_seed):
                if not args.dry_run:
                    parent_dir = os.path.dirname(dest_seed)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    shutil.copy2(src_seed, dest_seed)
                    if seed_file.startswith(".agents/"):
                        rel_seed = seed_file.replace(".agents/", "")
                        resolve_templates(target_agents_dir, manifest, target_files=[rel_seed])
                    else:
                        resolve_templates(target_dir, manifest, target_files=[seed_file])
                    print(f"  -> Seeded {seed_file}")
                else:
                    print(f"  [SIMULATED] -> Seeded {seed_file}")
            else:
                if not args.dry_run:
                    print(f"  -> Preserved existing {seed_file}")

    template_dir = os.path.join(foundation_dir, ".agents", "templates")
    if os.path.exists(template_dir):
        if not args.dry_run:
            target_template_dir = os.path.join(target_agents_dir, "templates")
            os.makedirs(target_template_dir, exist_ok=True)
            ai_brands_path = os.path.join(foundation_dir, ".agents", "canons", "global", "ai_brands.json")
            if os.path.exists(ai_brands_path):
                with open(ai_brands_path, "r", encoding="utf-8") as f:
                    ai_brands = json.load(f)
                
                ai_arg = getattr(args, "ai", "all")
                if not ai_arg or ai_arg.lower() == "all":
                    selected_ais = list(ai_brands.keys())
                else:
                    selected_ais = [x.strip() for x in ai_arg.split(",") if x.strip()]
                    if "agents" not in selected_ais and "agents" in ai_brands:
                        selected_ais.append("agents")
                deployed_ais_list = []
                
                for ai_name, brand in ai_brands.items():
                    if ai_name not in selected_ais:
                        continue
                    
                    deployed_ais_list.append(ai_name)
                    template_name = brand.get("template")
                    target_filename = brand.get("target_path")
                    
                    src_template = os.path.join(template_dir, template_name)
                    dest_template = os.path.join(target_template_dir, template_name)
                    
                    if os.path.exists(src_template):
                        shutil.copy2(src_template, dest_template)
                        resolve_templates(target_template_dir, manifest, target_files=[template_name])
            else:
                print("    [WARNING] ai_brands.json not found. Skipping root AI config propagation.")
            
            try:
                deployed_file = os.path.join(target_agents_dir, ".deployed_ais")
                project_name = os.path.basename(os.path.abspath(target_dir))
                with open(deployed_file, "w", encoding="utf-8") as df:
                    json.dump({
                        "project_name": project_name, 
                        "deployed_ais": deployed_ais_list,
                        "sync_results": {ai: {"status": "SUCCESS", "message": "Deployed"} for ai in deployed_ais_list}
                    }, df, indent=2)
            except Exception as e:
                print(f"    [WARNING] Could not write .deployed_ais: {e}")
                
            if not args.dry_run and deployed_ais_list:
                sync_ai_configs(target_dir, selected_ais=deployed_ais_list, dry_run=args.dry_run)
                
        else:
            print("  [SIMULATED] -> Processed Templates and propagated root AI configs")

    if not args.dry_run:
        print("  -> Initializing Orion Brain Graph...")
        orion_script = os.path.join(foundation_dir, ".agents", "scripts", "orion.py")
        if os.path.exists(orion_script):
            try:
                # 1. Initialize empty Graph Database
                subprocess.run([sys.executable, orion_script, "orion_ops", "init"], cwd=target_dir, check=True)
                
                # 2. Scaffold Base Context Directory to prevent amnesia
                context_dir = os.path.join(target_dir, "context")
                os.makedirs(context_dir, exist_ok=True)
                
                context_json = os.path.join(context_dir, "context.json")
                if not os.path.exists(context_json):
                    with open(context_json, "w", encoding="utf-8") as f:
                        json.dump({"state": "init", "evolution_overdue": False, "memory": []}, f, indent=2)
                        
                readme_md = os.path.join(target_dir, "README.md")
                if not os.path.exists(readme_md):
                    with open(readme_md, "w", encoding="utf-8") as f:
                        f.write(f"# {os.path.basename(os.path.abspath(target_dir))}\n\nProject initialized by Portable Brainvibing.\n")

                # 3. Auto-Hydrate Graph with Rules, Skills, and Context
                print("  -> Auto-Hydrating Rules & Context into Brain Graph...")
                subprocess.run([sys.executable, orion_script, "orion_ops", "ingest", ".agents", "context", "README.md"], cwd=target_dir, check=True)
                
            except Exception as e:
                print(f"    [WARNING] Failed to initialize Orion Brain Graph: {e}")
        else:
            print(f"    [WARNING] orion.py not found at {orion_script}")

    # 4. Proactive Git Hooks
    git_hooks_dir = os.path.join(target_dir, ".git", "hooks")
    if os.path.exists(git_hooks_dir):
        post_commit_path = os.path.join(git_hooks_dir, "post-commit")
        hook_script = "#!/bin/sh\n# Auto-sync Orion Brain Graph after commit\npython .agents/scripts/orion.py brain sync \"post-commit auto sync\" >/dev/null 2>&1 &\n"
        if not args.dry_run:
            try:
                existing_hook = ""
                if os.path.exists(post_commit_path):
                    with open(post_commit_path, "r", encoding="utf-8") as f:
                        existing_hook = f.read()
                
                if "orion.py brain sync" not in existing_hook:
                    with open(post_commit_path, "a" if existing_hook else "w", encoding="utf-8", newline="\n") as f:
                        if not existing_hook:
                            f.write(hook_script)
                        else:
                            f.write("\n# Auto-sync Orion Brain Graph after commit\npython .agents/scripts/orion.py brain sync \"post-commit auto sync\" >/dev/null 2>&1 &\n")
                    
                    if os.name != 'nt':
                        os.chmod(post_commit_path, 0o755)
                    print(f"  -> Injected post-commit Git hook at {post_commit_path}")
            except Exception as e:
                print(f"    [WARNING] Failed to inject post-commit hook: {e}")
        else:
            print("  [SIMULATED] -> Injected post-commit Git hook")
    else:
        print(f"    [WARNING] Target is not a Git repository (.git not found). Post-commit hooks will not be active.")

    print("\nDeployment Complete!")
    print("AI Agents in the target project are now connected to the Foundation.")
    print("⚡ [RECOMMENDED TIER: BUDGET] — Deploy operations are batch tasks. Switch back to Budget model for subsequent operations.")

# === PUSH UPSTREAM ===
def increment_patch_version(content):
    """
    Finds 'version: "x.y.z"' or 'version: x.y.z' and increments z.
    """
    version_pattern = r'^(version:\s*["\']?)(\d+\.\d+\.)(\d+)(["\']?)$'
    
    def replace_version(match):
        prefix = match.group(1)
        base = match.group(2)
        patch = int(match.group(3))
        suffix = match.group(4)
        return f"{prefix}{base}{patch + 1}{suffix}"

    new_content, count = re.subn(version_pattern, replace_version, content, flags=re.MULTILINE)
    return new_content, count > 0


def resolve_foundation_agents(project_agents: str) -> str:
    """
    Resolve target foundation .agents path from marker file when available.
    Supports marker values that point either to foundation root OR directly to .agents.
    """
    foundation_path_marker = os.path.join(project_agents, ".foundation_path")

    if not os.path.exists(foundation_path_marker):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".agents")

    with open(foundation_path_marker, "r", encoding="utf-8") as f:
        marker_path = f.read().strip()

    marker_path = os.path.abspath(marker_path)

    # Case A: marker already points to .agents directory.
    if os.path.basename(marker_path).lower() == ".agents":
        return marker_path

    # Case B: marker points to foundation root.
    return os.path.join(marker_path, ".agents")


def files_differ(src: str, dest: str) -> bool:
    if not os.path.exists(dest):
        return True
    with open(src, "rb") as f:
        src_bytes = f.read()
    with open(dest, "rb") as f:
        dest_bytes = f.read()
    return src_bytes != dest_bytes


def copy_with_optional_version_bump(local_file: str, foundation_file: str, file_name: str, dry_run: bool) -> bool:
    """
    Copy local file to foundation path. Returns True if a version bump happened.
    """
    if dry_run:
        return False

    os.makedirs(os.path.dirname(foundation_file), exist_ok=True)

    if file_name in VERSION_BUMP_FILES:
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                content = f.read()

            new_content, bumped = increment_patch_version(content)

            with open(foundation_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            return bumped
        except Exception as e:
            print(f"    [WARNING] Could not auto-bump {file_name}: {e}")
            shutil.copy2(local_file, foundation_file)
            return False

    shutil.copy2(local_file, foundation_file)
    return False

def cmd_upstream(args):
    print("========================================")
    print(" 🛑 AUTONOMOUS UPSTREAM MERGE DISABLED ")
    print("========================================")
    print("To prevent framework pollution, autonomous upstream merging is disabled.")
    print("The AI should draft fixes in .agents/LEARNINGS.md.")
    print("You must manually review LEARNINGS.md and route them to the Foundation:")
    print("")
    print("  1. Is this a Universal Law?")
    print("     -> Move to: _foundation/.agents/rules/")
    print("")
    print("  2. Is this a Framework Quirk?")
    print("     -> Move to: _foundation/.agents/canons/ecosystems/<framework>/")
    print("")
    print("Human validation prevents architectural corruption.")
    return True

# === SYNC AI CONFIGS ===
def sync_ai_configs(target_root: str, selected_ais: list | None = None, dry_run: bool = False):
    """
    Sync AI configuration files with latest foundation templates.
    
    Args:
        target_root: Path to target project
        selected_ais: List of AI names to sync. If None, syncs all deployed.
        dry_run: If True, simulate without writing
    
    Returns:
        dict: Sync results per AI
    """
    # Find foundation path
    foundation_path = get_foundation_path(target_root)
    if not foundation_path:
        if os.path.exists(os.path.join(target_root, ".agents", "templates", "AGENTS.template.md")):
            foundation_path = target_root
            print(" Running inside foundation.")
        else:
            print(" Error: Foundation path not found.")
            print("   This project may not be deployed from a foundation.")
            print("   Run foundation.py deploy first.")
            return {}
    
    if not os.path.exists(foundation_path):
        print(f" Error: Foundation not found at: {foundation_path}")
        return {}
    
    print(f" Foundation: {foundation_path}")
    
    # Determine which AIs to sync
    if selected_ais is None:
        # Try to load from tracking file
        deployed = load_deployed_ais(target_root)
        if deployed:
            selected_ais = deployed
            print(f" Syncing deployed AIs: {', '.join(selected_ais)}")
        else:
            # Default to all
            selected_ais = list(AI_CONFIGS.keys())
            print(f" Syncing all AIs (no tracking file found)")
    
    # Get project name
    project_name = os.path.basename(os.path.abspath(target_root))
    
    # Sync each AI
    results = {}
    source_templates = os.path.join(foundation_path, ".agents", "templates")
    
    print(f"\n Syncing AI configurations...")
    if dry_run:
        print(" [DRY RUN] No files will be modified.\n")
    
    # Read project manifest if available
    manifest = {}
    manifest_path = os.path.join(target_root, ".agents", ".project_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except Exception as _e:
            _log_telemetry(_e, 'foundation.py:797')

    for ai_name in selected_ais:
        if ai_name not in AI_CONFIGS:
            results[ai_name] = {"status": "ERROR", "message": f"Unknown AI: {ai_name}"}
            continue
        
        config = AI_CONFIGS[ai_name]
        template_path = os.path.join(source_templates, config["template"])
        
        if not os.path.exists(template_path):
            results[ai_name] = {"status": "ERROR", "message": "Template not found"}
            print(f"    {ai_name}: Template not found")
            continue
        
        # Build target path
        if config["target_dir"]:
            target_path = os.path.join(target_root, config["target_dir"], os.path.basename(config["target_path"]))
        else:
            target_path = os.path.join(target_root, config["target_path"])
        
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            # Read template
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Smart merge
            content, status = smart_merge_config(
                template_content,
                target_path,
                project_name,
                config["format"],
                dry_run,
                manifest
            )
            
            if content is None:
                results[ai_name] = {"status": "SKIPPED", "message": status}
                print(f"    {ai_name}: {status}")
            else:
                results[ai_name] = {"status": "SUCCESS", "message": status}
                print(f"   {ai_name}: {status}{' (SIMULATED)' if dry_run else ''}")
        except Exception as e:
            results[ai_name] = {"status": "ERROR", "message": str(e)}
            print(f"   {ai_name}: {e}")
    
    # Update tracking file
    if not dry_run:
        deployed_file = os.path.join(target_root, ".agents", ".deployed_ais")
        try:
            data = {"project_name": project_name, "deployed_ais": selected_ais, "sync_results": results}
            with open(deployed_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"\n  Warning: Could not update tracking file: {e}")
    
    print(f"\n Sync completed{' (SIMULATED)' if dry_run else ''}.")
    return results


def cmd_sync_ai(args):
    selected_ais = args.ai.split(",") if getattr(args, "ai", None) else None
    sync_ai_configs(args.target, selected_ais=selected_ais, dry_run=args.dry_run)

# === CLI ===
def main():
    parser = argparse.ArgumentParser(description="Foundation Package & Deployment Manager")
    subparsers = parser.add_subparsers(dest="command")
    
    # Deploy
    parser_deploy = subparsers.add_parser("deploy", help="Deploy Foundation to a target project")
    parser_deploy.add_argument("--target", required=True, help="Target project root directory")
    parser_deploy.add_argument("--framework", default=None, help="Framework (e.g., react, flutter, python, node). Auto-detected if omitted.")
    parser_deploy.add_argument("--language", default=None, help="Language (e.g., typescript, dart, python). Auto-detected if omitted.")
    parser_deploy.add_argument("--ai", default="all", help="Comma-separated list of AIs to deploy (or 'all'). Defaults to 'all'.")
    parser_deploy.add_argument("--dry-run", action="store_true", help="Simulate deployment without modifying files")
    parser_deploy.add_argument("--use-local-llm", action="store_true", help="Flag to indicate if using a local LLM")
    parser_deploy.add_argument("--llm-params", type=float, default=0.0, help="Parameter size of the local LLM in Billions (e.g., 8.0, 70.0)")
    
    # Push Upstream
    parser_upstream = subparsers.add_parser("push-upstream", help="Sync local project changes back to Foundation")
    parser_upstream.add_argument("--project", "--source", default=".", dest="project", help="Path to the local project root")
    parser_upstream.add_argument("--dry-run", action="store_true", help="Simulate sync without modifying files")
    parser_upstream.add_argument("--force-hub-override", action="store_true", help="Force overwriting generic hub templates with spoke-resolved assets")
    
    # Sync AI
    parser_syncai = subparsers.add_parser("sync-ai", help="Sync AI brand configs to local templates")
    parser_syncai.add_argument("--target", required=True, help="Target project root directory")
    parser_syncai.add_argument("--ai", help="Comma-separated list of AIs to sync")
    parser_syncai.add_argument("--dry-run", action="store_true", help="Simulate sync without modifying files")

    args = parser.parse_args()
    
    if args.command == "deploy":
        cmd_deploy(args)
    elif args.command == "push-upstream":
        cmd_upstream(args)
    elif args.command == "sync-ai":
        cmd_sync_ai(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
