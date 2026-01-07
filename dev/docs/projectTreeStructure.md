# Project Tree Structure

Last Updated: 2026-01-05  
Status: Phase 3 Deployed | Phase 4 Ready | Ollama Cloud API Integrated | JSON Refactored

---

```
SparksBM/
├── Agentic Framework/                    # Core AI Engine (Python)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── baseAgent.py                  # Base class for all agents
│   │   ├── mainAgent.py                  # Main orchestrator
│   │   ├── helpers.py                    # Phase 1: Helper functions
│   │   ├── instructions.py               # Agent instructions
│   │   ├── ismsHandler.py                # ISMS operation handler
│   │   ├── excelDoc.py                   # Excel document agent
│   │   ├── pdfDoc.py                     # PDF document agent
│   │   ├── wordDoc.py                    # Word document agent
│   │   └── coordinators/                 # Coordinator pattern
│   │       ├── __init__.py
│   │       ├── documentCoordinator.py    # Phase 2: Document processing
│   │       └── ismsCoordinator.py        # Phase 4: ISMS operations (READY)
│   │
│   ├── orchestrator/                     # Orchestration layer
│   │   ├── __init__.py
│   │   ├── chatRouter.py                 # Phase 3: Routing logic (DEPLOYED)
│   │   ├── reasoningEngine.py            # Ollama: LLM interface (COMPLETE)
│   │   ├── executor.py                   # Action executor
│   │   ├── intentClassifier.py           # LLM-based intent classification
│   │   ├── queryPlanner.py               # Query planning
│   │   └── toolChain.py                  # Tool chain management
│   │
│   ├── tools/                            # Tool implementations
│   │   ├── __init__.py
│   │   ├── veriniceTool.py               # Verinice ISMS API integration
│   │   ├── llmTool.py                    # LLM integration (Gemini/OpenAI)
│   │   ├── excelTool.py                  # Excel file processing
│   │   ├── wordTool.py                   # Word file processing
│   │   ├── pdfTool.py                    # PDF file processing
│   │   ├── documentQueryTool.py          # Document querying
│   │   └── intelligentOrchestrator.py    # Intelligent orchestration
│   │
│   ├── presenters/                       # Response formatting
│   │   ├── __init__.py
│   │   ├── base.py                       # Base presenter
│   │   ├── text.py                       # Text formatting
│   │   ├── table.py                      # Table formatting
│   │   ├── list.py                       # List formatting
│   │   ├── report.py                     # Report formatting
│   │   └── error.py                      # Error formatting
│   │
│   ├── memory/                           # Memory and context management
│   │   ├── __init__.py
│   │   ├── conversation.py               # Conversation history
│   │   ├── enhancedContextManager.py     # Context management
│   │   ├── memoryStore.py                # Memory storage
│   │   ├── selections.py                 # User selections
│   │   └── uiState.py                    # UI state management
│   │
│   ├── config/                           # Configuration
│   │   ├── __init__.py
│   │   └── settings.py                   # System settings
│   │
│   ├── utils/                            # Utilities & Configuration
│   │   ├── __init__.py
│   │   ├── pathUtils.py                  # Path utilities
│   │   ├── ismsInstructions.json        # ISMS operation patterns
│   │   ├── documentsInstructions.json    # Document processing patterns
│   │   ├── commonInstructions.json      # Shared patterns (conversational, capabilities)
│   │   ├── errorsBase.json               # Error message templates
│   │   └── knowledgeBase.json            # Knowledge base content
│   │
│   ├── main.py                           # Entry point
│   └── requirements.txt                  # Python dependencies
│
├── NotebookLLM/                          # Web API & Frontend (FastAPI + Vue/Nuxt)
│   ├── api/                              # FastAPI Backend
│   │   ├── __init__.py
│   │   ├── main.py                       # API entry point
│   │   │
│   │   ├── routers/                      # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                   # Chat and file upload endpoints
│   │   │   └── monitoring.py             # Phase 3 routing logs endpoint
│   │   │
│   │   ├── services/                     # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── agentService.py           # Agent orchestration service
│   │   │   └── sessionService.py         # Session management
│   │   │
│   │   ├── models/                       # Pydantic models
│   │   │   ├── __init__.py
│   │   │   └── chat.py                   # Chat request/response models
│   │   │
│   │   ├── middleware/                   # API middleware
│   │   │   └── __init__.py
│   │   │
│   │   ├── utils/                        # API utilities
│   │   │   └── __init__.py
│   │   │
│   │   ├── uploads/                      # Uploaded files directory
│   │   └── requirements.txt              # API dependencies
│   │
│   ├── integration/                      # Framework integration
│   │   ├── agentBridge.py                # Agentic Framework bridge
│   │   ├── contextMapper.py              # Context mapping
│   │   └── responseFormatter.py          # Response formatting
│   │
│   ├── frontend/                         # Nuxt.js Vue Frontend
│   │   ├── app.vue                       # Root app component
│   │   ├── nuxt.config.ts                # Nuxt configuration
│   │   ├── nuxt.d.ts                     # Nuxt TypeScript definitions
│   │   ├── tsconfig.json                 # TypeScript configuration
│   │   ├── package.json                  # Frontend dependencies
│   │   ├── package-lock.json             # Locked dependencies
│   │   │
│   │   ├── pages/                        # Page components
│   │   │   └── index.vue                 # Main chat page
│   │   │
│   │   ├── layouts/                      # Layout components
│   │   │   └── notebook.vue              # Notebook layout (with table scrolling)
│   │   │
│   │   ├── components/                   # Reusable components
│   │   │   └── layout/
│   │   │       └── AppLogoDesktop.vue    # Logo component
│   │   │
│   │   ├── composables/                  # Vue composables
│   │   │   └── useApi.ts                 # API client composable
│   │   │
│   │   ├── plugins/                      # Nuxt plugins
│   │   │   └── vuetify.ts                # Vuetify plugin
│   │   │
│   │   ├── types/                        # TypeScript types
│   │   │   └── isms.ts                   # ISMS type definitions
│   │   │
│   │   └── public/                       # Static assets
│   │       └── logo.png                  # Application logo
│   │
│   ├── config/                           # Configuration
│   │   ├── notebookllm.env               # Environment variables
│   │   └── notebookllm.env.example       # Example environment file
│   │
│   └── start.sh                          # Startup script
│
├── SparksbmISMS/                         # ISMS Backend (Java/Kotlin + Vue)
│   ├── config/                           # Configuration
│   │   ├── sparksbm.env                  # Environment variables
│   │   └── sparksbm.env.example          # Example environment file
│   │
│   ├── keycloak/                         # Keycloak authentication
│   │   ├── docker-compose.yml            # Keycloak Docker setup
│   │   ├── themes/                       # Keycloak themes
│   │   └── update-master-realm.sh        # Realm update script
│   │
│   ├── scripts/                          # Management scripts
│   │   ├── sparksbmMgmt.py               # Python API client
│   │   ├── requirements.txt              # Script dependencies
│   │   └── domain-templates/             # Domain templates
│   │       ├── iso-27001-template.json   # ISO 27001
│   │       ├── iso-22301-template.json   # ISO 22301
│   │       ├── gdpr-template.json        # GDPR
│   │       └── nis-2-template.json       # NIS-2
│   │
│   ├── verinice-veo/                     # Verinice VEO Backend (Java/Gradle)
│   ├── verinice-veo-forms/               # Verinice Forms (Kotlin)
│   ├── verinice-veo-history/             # Verinice History (Kotlin)
│   ├── verinice-veo-web/                 # Verinice Web Frontend (Vue/TypeScript)
│   │   └── components/
│   │       └── ChatbotWidget.vue         # Chatbot widget (with table scrolling)
│   │
│   ├── start-sparksbm.sh                 # Start all ISMS services
│   └── stop-sparksbm.sh                  # Stop all ISMS services
│
└── dev/                                  # Development files
    ├── docs/                             # Documentation (.md files)
    │   ├── todo.md                       # Current TODO list
    │   ├── qaBugReport.md                # Bug tracking & test results
    │   ├── systemArchitecture.md         # System architecture
    │   ├── projectTreeStructure.md       # This file
    │   ├── ollamaIntegration.md          # Ollama Cloud API integration
    │   ├── refactoringMonitoringLog.md   # Refactoring changelog
    │   ├── RENDER_DEPLOYMENT_GUIDE.md    # Render deployment guide
    │   ├── TEST_FILES_GUIDE.md           # Test files documentation
    │   ├── agentResponseAudit.md         # Agent response audit
    │   └── ... (other documentation files)
    │
    ├── test/                             # Test scripts
    │   ├── comprehensiveISMSTest.py      # Comprehensive ISMS tests
    │   ├── edgeCaseTest.py               # Edge case tests
    │   ├── integrationTest.py            # Full integration tests
    │   ├── masterTestSuite.py            # Master test runner (Phase 3 & 4)
    │   ├── phase4ValidationTest.py       # Phase 4 ISMS coordinator tests
    │   └── testKeycloakAuth.py          # Keycloak authentication tests
    │
    ├── integration/                      # Production-ready scripts (flat structure)
    │   ├── dailyMonitor.py               # Daily system health monitoring
    │   ├── deploymentMonitor.py          # Deployment monitoring script
    │   ├── monitorOllamaUsage.py          # Ollama Cloud API usage monitoring
    │   └── setup-daily-monitoring.sh      # Setup script for daily monitoring
    │
    ├── logs/                             # Log files
    │   └── ollama/                       # Ollama usage logs
    │       └── usage_YYYYMMDD.json       # Daily usage statistics
    │
    └── logo.png                          # Development logo
```
