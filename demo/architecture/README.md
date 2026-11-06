# Claims architecture diagrams

- **Current implementation:** [Local architecture](claims-current-architecture.svg).
- **Proposed Azure vision (not deployed):** [Azure target architecture](claims-proposed-azure-architecture.svg).
- PowerPoint previews: [slide 48](deck-slide-48.png), [slide 49](deck-slide-49.png) (1920 × 1080).
- Editable versions are slides **48–49** in the [presentation](../../.customerquestion/Selective/AzureContentUnderstanding.PPTX), at the end of **Demos**, before Resources.

The presentation link is local/private: the customer deck is excluded from Git.
The standalone SVGs and PNG previews are the shareable repository assets.

Shapes, text and arrows are native editable PowerPoint components; service icons are vector SVG pictures. The standalone diagrams embed their icons and have no external dependencies.

## Three-layer layout

Both diagrams use the same reading order and service positions:

1. **Preprocessing at the top.** Evidence parsing/deduplication, chunking, embedding requests, persisted artifacts and Search uploads. The current pipeline runs locally. **All target preprocessing executes inside one Azure Databricks Workflows boundary**, using jobs/notebooks, on demand or on a schedule. The single Databricks icon represents the entire pipeline; the Blob/ADLS input icon represents storage, not another processing runtime. Databricks calls the AI endpoints, persists outputs in Blob/ADLS, and writes the Search index.
2. **Shared connected services in the middle.** A single Foundry account contains Content Understanding, the embedding deployment and the chat/reasoning deployment. Search and the structured-data tool remain outside that account boundary.
3. **Online inference at the bottom.** Claims Explorer exchanges questions and cited answers with the claims agent. The current agent runs locally in FastAPI. The proposed agent runs **natively in Microsoft Foundry Agent Service**, as either a **prompt agent** or a **hosted agent**. These are implementation alternatives, not two simultaneous agents. Its model/tool runtime uses the same embedding deployment for query vectors, the chat model, claim-filtered semantic hybrid Search, and a read-only structured-data tool.

The bottom layer is generative inference, not an implemented risk score or automated claim decision. Rectangles express logical ownership or runtime grouping, not virtual networks or private endpoints.

## One Foundry account, distinct API endpoints

The demo's **same Foundry account**, `ais-foundry-eval-dev-02`, supplies:

| Capability | Endpoint / deployment |
|---|---|
| Content Understanding | `https://ais-foundry-eval-dev-02.services.ai.azure.com/` |
| All Azure OpenAI models | `https://ais-foundry-eval-dev-02.openai.azure.com/` |
| Ingestion and query embeddings | `text-embedding-3-large`, at the same OpenAI endpoint above |
| Chat/reasoning | `gpt-5.2`, at the same OpenAI endpoint above |

Different API hostnames do **not** mean different accounts. CU's current prebuilt-model defaults also map to this account's `gpt-5.2` and `text-embedding-3-large` deployments.

The Foundry **project**, `proj-foundry-standard-dev-02`, provides connections and trace visibility. In the current demo it holds an external-agent metadata registration; in the target it owns the **native Agent Service agent**. These are different hosting arrangements. AI Search is a separate project-connected resource; neither Search, Databricks Genie nor Application Insights is depicted as a model deployment inside the Foundry account.

## Arrow semantics

| Line | Meaning | Examples |
|---|---|---|
| Solid blue, one arrowhead | Evidence/data movement or returned data/answers | CU -> preprocessing: native content; embeddings -> caller: vectors; preprocessing -> Search: index upload; agent -> UI: cited answer |
| Dashed black, one arrowhead | An API request, from caller to service | Preprocessing -> CU: analyze; agent -> embeddings: embed query; agent -> Search: hybrid query; agent -> Genie/API: read |
| Dotted gray, one arrowhead | Telemetry export | Agent -> Application Insights |

API calls and their data returns have **separate arrows in opposite directions**. There are no implicit reversed replies or undirected lines. In the current diagram, the artifact-to-Search arrow represents data uploaded by the local preprocessing task; in the target, the complete Databricks workflow uploads the records. Neither arrow implies storage autonomously indexing itself. Native Content Understanding results return to preprocessing; CU does not call the chunking worker, and the diagram does not invent a direct CU-to-Search ingestion path.

The current structured API is actual loopback HTTP over authored synthetic six-claim records. The target uses read-only Databricks Genie MCP over governed Delta claim tables and log notes under Unity Catalog. These are not equivalent implementations. The target does **not** host its agent on Azure Container Apps or an independently deployed FastAPI server. Web UI or gateway hosting is independent and is not selected by this diagram.

For a prompt agent, managed Search/tool integration can perform the depicted query-embedding step on the agent's behalf; a hosted agent can implement it in code. Tool/index configuration, authentication and behavior must be validated for the chosen agent type. The arrows express the logical model/data exchanges, not a claim that both agent implementations use identical internal SDK calls.

Azure Monitor OpenTelemetry exports the current demo's spans to the project's Application Insights. Native Agent Service monitoring and hosted instrumentation, as applicable, provide the proposed agent's telemetry. Foundry exposes correlated traces through project monitoring; the diagram does not imply a serial Application Insights-to-Foundry inference call. The current external-agent registration is metadata, not hosted compute. Speaker notes retain implementation details, authentication and design caveats.

## Visual scale

The final slides use 22-point titles, 11-point section headings, approximately 9.75-point component labels, and consistent 32-point service icons. Main connectors are 0.75 point; telemetry and ownership boundaries are 0.6 point. Source SVGs and native PowerPoint components use the same reduced visual hierarchy. Labels, line patterns and destination arrowheads are checked after rendering.

## Architecture Center visual references

The redraw follows the visual conventions of these actual Microsoft diagrams, rather than a dashboard/card layout:

- [Basic Microsoft Foundry chat reference architecture](https://learn.microsoft.com/azure/architecture/ai-ml/architecture/basic-microsoft-foundry-chat) and its [diagram](https://learn.microsoft.com/azure/architecture/ai-ml/architecture/_images/openai-end-to-end-basic.svg).
- [Baseline Microsoft Foundry chat reference architecture](https://learn.microsoft.com/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat) and its [diagram](https://learn.microsoft.com/azure/architecture/ai-ml/architecture/_images/baseline-microsoft-foundry.svg).

These are **visual references**, not a claim that the current demo implements their network isolation, resilience or managed hosting. Native Agent Service hosting is proposed only. The supported [prompt and hosted agent types](https://learn.microsoft.com/azure/foundry/agents/overview#agent-types) inform the target diagram.

## Icon provenance

Unmodified Microsoft official Azure Architecture Center V25 SVG icons:

- Guidance and terms: https://learn.microsoft.com/en-us/azure/architecture/icons/
- Official download: https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V25.zip

Product icons identify their corresponding Microsoft products. Content Understanding uses the official Cognitive Services family icon; the target agent uses the official Foundry Agent Service icon. The custom local application uses Microsoft's generic browser, code, files and input/output icons. No application or service logo has been fabricated.

## Preservation

The 58 original slide parts and their supporting parts are retained byte-for-byte, including animations. Only four original package metadata parts change: presentation ordering/sections, presentation relationships, content types and the slide-count property. No application, notebook or live Azure resource is changed by this deck work.
