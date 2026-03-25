# Repo Map: DevHub V2

- Fingerprint: 0ccba5d68303ef7e0e385650f04144099a203c40
- Indexed files: 9160

## Top Directories
- `data`: 9066 files
- `backend`: 70 files
- `frontend`: 22 files
- `docs`: 2 files

## Important Files
- `data/projects/907e8dfa-1998-4afe-908d-de23e9371dc4/src/node/main.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 245 lines. Primary symbol: mod. Key imports: import { field, logger } from "@coder/logger", import http from "http", import * as os from "os", import * as path from "path", import { Disposable } from "../common/emitter". Routes/endpoints: /. Data models/types: OpenCommandPipeArgs. Representative commands: gotoLineMode?: boolean, gotoLineMode: true,, pipeArgs.folderURIs.push(fp), pipeArgs.fileURIs.push(fp).
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/tlon/src/monitor/index.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 1430 lines. Primary symbol: core. Key imports: import type { RuntimeEnv, ReplyPayload, OpenClawConfig } from "../../api.js";, import { createLoggerBackedRuntime } from "../../api.js";, import { getTlonRuntime } from "../runtime.js";, import { createSettingsManager, type TlonSettingsStore } from "../settings.js";, import { normalizeShip, parseChannelNest } from "../targets.js";. Routes/endpoints: /v2, /v3, /v1/news, /groups/ui, /v1/foreigns. Data models/types: MonitorTlonOpts. Representative comman
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/whatsapp/src/monitor-inbox.test-harness.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 226 lines. Primary symbol: sessionState. Key imports: import { EventEmitter } from "node:events";, import fsSync from "node:fs";, import os from "node:os";, import path from "node:path";, import { resetLogger, setLoggerOverride } from "openclaw/plugin-sdk/runtime-env";. Routes/endpoints: /tmp/mid. Data models/types: AnyMockFn, MockSock, MonitorWebInbox, InboxOnMessage.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/src/infra/exec-approvals-store.test.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 248 lines. Primary symbol: requestJsonlSocketMock. Key imports: import fs from "node:fs";, import path from "node:path";, import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";, import { makeTempDir } from "./exec-approvals-test-helpers.js";, import type { ExecApprovalsFile } from "./exec-approvals.js";. Routes/endpoints: /tmp/a.sock, /tmp/b.sock. Data models/types: ExecApprovalsModule.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/src/memory/index.test.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 1329 lines. Primary symbol: embedText. Key imports: import { randomUUID } from "node:crypto";, import { mkdirSync, rmSync } from "node:fs";, import fs from "node:fs/promises";, import os from "node:os";, import path from "node:path";. Routes/endpoints: extra/extra.md. Data models/types: MemoryIndexModule. Representative commands: shouldFallbackOnError: (message: string) => boolean;.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/src/secrets/apply.test.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 763 lines. Primary symbol: OPENAI_API_KEY_ENV_REF. Key imports: import fs from "node:fs/promises";, import os from "node:os";, import path from "node:path";, import { afterEach, beforeEach, describe, expect, it } from "vitest";, import { runSecretsApply } from "./apply.js";. Routes/endpoints: models.providers.openai.apiKey, profiles.openai:default.key, profiles.openai:bot.token, models.providers.openai.dev.apiKey, skills.entries.qa-secret-test.apiKey, talk.apiKey. Data models/types: ApplyFixture.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/src/gateway/hooks-mapping.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 526 lines. Key imports: import fs from "node:fs";, import path from "node:path";, import { CONFIG_PATH, type HookMappingConfig, type HooksConfig } from "../config/config.js";, import { importFileModule, resolveFunctionModuleExport } from "../hooks/module-loader.js";, import type { HookMessageChannel } from "./hooks.js";. Routes/endpoints: gmail. Data models/types: HookMappingResolved, HookMappingTransformResolved, HookMappingContext, HookAction, HookMappingResult, HookTransformResult.
- `data/projects/907e8dfa-1998-4afe-908d-de23e9371dc4/src/node/vscodeSocket.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 206 lines. Primary symbol: router. Key imports: import { logger } from "@coder/logger", import express from "express", import * as http from "http", import * as path from "path", import { HttpCode, HttpError } from "../common/http". Routes/endpoints: /session?filePath=, /add-session. Data models/types: EditorSessionEntry, DeleteSessionRequest, AddSessionRequest, GetSessionResponse.
- `data/projects/907e8dfa-1998-4afe-908d-de23e9371dc4/src/node/routes/vscode.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 258 lines. Primary symbol: mod. Key imports: import { logger } from "@coder/logger", import * as crypto from "crypto", import * as express from "express", import { promises as fs } from "fs", import * as http from "http". Routes/endpoints: /, /manifest.json, /mint-key. Data models/types: IVSCodeServerAPI, VSCodeModule. Representative commands: short_name: req.args["app-name"],.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/bluebubbles/src/account-resolve.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 52 lines. Primary symbol: account. Key imports: import { resolveBlueBubblesAccount } from "./accounts.js";, import type { OpenClawConfig } from "./runtime-api.js";, import { normalizeResolvedSecretInputString } from "./secret-input.js";. Routes/endpoints: channels.bluebubbles.serverUrl, channels.bluebubbles.password. Data models/types: BlueBubblesAccountResolveOpts.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/bluebubbles/src/attachments.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 298 lines. Primary symbol: DEFAULT_ATTACHMENT_MAX_BYTES. Key imports: import crypto from "node:crypto";, import path from "node:path";, import { resolveBlueBubblesServerAccount } from "./account-resolve.js";, import { assertMultipartActionOk, postMultipartFormData } from "./multipart.js";, import {. Routes/endpoints: /api/v1/message/attachment. Data models/types: BlueBubblesAttachmentOpts, MediaFetchErrorCode, SendBlueBubblesAttachmentResult.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/bluebubbles/src/probe.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 164 lines. Primary symbol: MAX_SERVER_INFO_CACHE_SIZE. Key imports: import type { BaseProbeResult } from "./runtime-api.js";, import { normalizeSecretInputString } from "./secret-input.js";, import { buildBlueBubblesApiUrl, blueBubblesFetchWithTimeout } from "./types.js";. Routes/endpoints: /api/v1/server/info, /api/v1/ping. Data models/types: BlueBubblesProbe, BlueBubblesServerInfo.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/bluebubbles/src/reactions.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 182 lines. Primary symbol: REACTION_TYPES. Key imports: import { resolveBlueBubblesServerAccount } from "./account-resolve.js";, import { getCachedBlueBubblesPrivateApiStatus } from "./probe.js";, import type { OpenClawConfig } from "./runtime-api.js";, import { blueBubblesFetchWithTimeout, buildBlueBubblesApiUrl } from "./types.js";. Routes/endpoints: /api/v1/message/react. Data models/types: BlueBubblesReactionOpts.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/bluebubbles/src/send.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 532 lines. Primary symbol: resolveEffectId. Key imports: import crypto from "node:crypto";, import { resolveBlueBubblesAccount } from "./accounts.js";, import {, import type { OpenClawConfig } from "./runtime-api.js";, import { stripMarkdown } from "./runtime-api.js";. Routes/endpoints: /api/v1/chat/query, /api/v1/chat/new, /api/v1/message/text. Data models/types: BlueBubblesSendOpts, BlueBubblesSendResult, PrivateApiDecision, BlueBubblesChatRecord.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/feishu/src/accounts.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 334 lines. Primary symbol: normalizeString. Key imports: import {, import { coerceSecretRef } from "openclaw/plugin-sdk/config-runtime";, import type { ClawdbotConfig } from "../runtime-api.js";, import type {. Routes/endpoints: channels.feishu.appId, channels.feishu.appSecret, channels.feishu.encryptKey, channels.feishu.verificationToken. Data models/types: FeishuCredentialResolutionMode, FeishuResolvedSecretRef.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/msteams/src/monitor.lifecycle.test.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 218 lines. Primary symbol: expressControl. Key imports: import { EventEmitter } from "node:events";, import { afterEach, describe, expect, it, vi } from "vitest";, import type { OpenClawConfig, RuntimeEnv } from "../runtime-api.js";, import type { MSTeamsConversationStore } from "./conversation-store.js";, import type { MSTeamsPollStore } from "./polls.js";. Routes/endpoints: /api/messages. Data models/types: FakeServer.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/msteams/src/token.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 40 lines. Primary symbol: appId. Key imports: import type { MSTeamsConfig } from "../runtime-api.js";, import {. Routes/endpoints: channels.msteams.appPassword. Data models/types: MSTeamsCredentials.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/telegram/src/bot.create-telegram-bot.test-harness.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 568 lines. Primary symbol: actual. Key imports: import { resolveDefaultModelForAgent } from "openclaw/plugin-sdk/agent-runtime";, import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";, import { resetInboundDedupe } from "openclaw/plugin-sdk/reply-runtime";, import type { MsgContext } from "openclaw/plugin-sdk/reply-runtime";, import type { GetReplyOptions, ReplyPayload } from "openclaw/plugin-sdk/reply-runtime";. Routes/endpoints: media/file.jpg. Data models/types: AnyMock, Any
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/telegram/src/bot.media.e2e-harness.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 252 lines. Primary symbol: defaultUndiciFetch. Key imports: import path from "node:path";, import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";, import { resetInboundDedupe } from "openclaw/plugin-sdk/reply-runtime";, import type { GetReplyOptions, MsgContext } from "openclaw/plugin-sdk/reply-runtime";, import { beforeEach, vi, type Mock } from "vitest";. Routes/endpoints: /tmp/telegram-media. Data models/types: TelegramBotRuntimeForTest, DispatchReplyWithBufferedBlockDispatch
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/telegram/src/token.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 102 lines. Primary symbol: accountId. Key imports: import { resolveNormalizedAccountEntry } from "openclaw/plugin-sdk/account-resolution";, import type { BaseTokenResolution } from "openclaw/plugin-sdk/channel-contract";, import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";, import { tryReadSecretFileSync } from "openclaw/plugin-sdk/infra-runtime";, import { DEFAULT_ACCOUNT_ID, normalizeAccountId } from "openclaw/plugin-sdk/routing";. Routes/endpoints: channels.telegram.botTok
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/tlon/src/channel.runtime.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 243 lines. Primary symbol: ssrfPolicy. Key imports: import crypto from "node:crypto";, import type { ChannelAccountSnapshot } from "openclaw/plugin-sdk/channel-contract";, import type { ChannelOutboundAdapter } from "openclaw/plugin-sdk/channel-send-result";, import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";, import type { ChannelPlugin } from "openclaw/plugin-sdk/core";. Routes/endpoints: /~/name. Data models/types: ResolvedTlonAccount, ConfiguredTlonAccount. Representativ
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/tlon/src/settings.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 391 lines. Primary symbol: SETTINGS_DESK. Key imports: import type { UrbitSSEClient } from "./urbit/sse-client.js";. Routes/endpoints: /desk/. Data models/types: PendingApproval, TlonSettingsStore, TlonSettingsState. Representative commands: showModelSig?: boolean;, showModelSig: typeof settings.showModelSig === "boolean" ? settings.showModelSig : undefined,.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/tlon/src/urbit/auth.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 48 lines. Primary symbol: cookie. Key imports: import type { LookupFn, SsrFPolicy } from "../../api.js";, import { UrbitAuthError } from "./errors.js";, import { urbitFetch } from "./fetch.js";. Routes/endpoints: /~/login. Data models/types: UrbitAuthenticateOptions.
- `data/projects/f6a79518-cef7-4750-a8ab-1710bfdf7402/extensions/voice-call/src/tunnel.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 314 lines. Primary symbol: args. Key imports: import { spawn } from "node:child_process";, import { getTailscaleDnsName } from "./webhook/tailscale.js";. Routes/endpoints: /voice/webhook. Data models/types: TunnelConfig, TunnelResult.

## Project Instructions
- `.devhub/DEVHUB.md`

## Detected Routes
- `/`
- `/v2`
- `/v3`
- `/v1/news`
- `/groups/ui`
- `/v1/foreigns`
- `/tmp/mid`
- `/tmp/a.sock`
- `/tmp/b.sock`
- `extra/extra.md`
- `models.providers.openai.apiKey`
- `profiles.openai:default.key`
- `profiles.openai:bot.token`
- `models.providers.openai.dev.apiKey`
- `skills.entries.qa-secret-test.apiKey`
- `talk.apiKey`
- `agents.list.0.memorySearch.remote.apiKey`
- `models.providers.openai.baseUrl`
- `skills.entries.__proto__.apiKey`
- `/tmp/old-secrets.json`

## Detected Models / Types
- `OpenCommandPipeArgs`
- `MonitorTlonOpts`
- `AnyMockFn`
- `MockSock`
- `MonitorWebInbox`
- `InboxOnMessage`
- `ExecApprovalsModule`
- `MemoryIndexModule`
- `ApplyFixture`
- `HookMappingResolved`
- `HookMappingTransformResolved`
- `HookMappingContext`
- `HookAction`
- `HookMappingResult`
- `HookTransformResult`
- `HookTransformFn`
- `EditorSessionEntry`
- `DeleteSessionRequest`
- `AddSessionRequest`
- `GetSessionResponse`

## Repo Tree
```text
DevHub V2/
|- backend
|  |- agents
|  |  |- migrations
|  |  |  `- __init__.py
|  |  |- __init__.py
|  |  |- admin.py
|  |  |- apps.py
|  |  |- architect.py
|  |  |- base.py
|  |  |- coder.py
|  |  |- deep_documentation.py
|  |  |- documentation.py
|  |  |- explorer.py
|  |  |- feature.py
|  |  |- memory.py
|  |  |- models.py
|  |  |- planner.py
|  |  |- reviewer.py
|  |  |- scaffolder.py
|  |  |- tests.py
|  |  |- views.py
|  |  `- workspace.py
|  |- api
|  |  |- migrations
|  |  |  `- __init__.py
|  |  |- __init__.py
|  |  |- admin.py
|  |  |- apps.py
|  |  |- models.py
|  |  |- tests.py
|  |  |- urls.py
|  |  `- views.py
|  |- core
|  |  |- migrations
|  |  |  |- 0001_initial.py
|  |  |  |- 0002_project_workspace_id.py
|  |  |  |- 0003_agent_memory_models.py
|  |  |  |- 0004_documentation_models.py
|  |  |  |- 0005_project_ai_config.py
|  |  |  |- 0006_chatmessage_metadata.py
|  |  |  `- __init__.py
|  |  |- __init__.py
|  |  |- admin.py
|  |  |- apps.py
|  |  |- models.py
|  |  |- tests.py
|  |  `- views.py
|  |- devhub_backend
|  |  |- __init__.py
|  |  |- asgi.py
|  |  |- settings.py
|  |  |- urls.py
|  |  `- wsgi.py
|  |- editor
|  |  |- migrations
|  |  |  `- __init__.py
|  |  |- __init__.py
|  |  |- admin.py
|  |  |- apps.py
|  |  |- consumers.py
|  |  |- models.py
|  |  |- routing.py
|  |  |- tests.py
|  |  `- views.py
|  |- integrations
|  |  |- migrations
|  |  |  `- __init__.py
|  |  |- __init__.py
|  |  |- admin.py
|  |  |- apps.py
|  |  |- models.py
|  |  |- tests.py
|  |  `- views.py
|  |- sandbox
|  |  |- migrations
|  |  |  `- __init__.py
|  |  |- __init__.py
|  |  |- admin.py
|  |  |- apps.py
|  |  |- executor.py
|  |  |- models.py
|  |  |- tests.py
|  |  `- views.py
|  `- manage.py
|- data
|  |- projects
|  |  |- 053d990f-343c-4061-bf45-208e50d9a993
|  |  |  |- backend
|  |  |  |  |- urls.py
|  |  |  |  `- views.py
|  |  |  |- src
|  |  |  |  |- components
|  |  |  |  |  |- Button.js
|  |  |  |  |  `- Calculator.js
|  |  |  |  `- App.js
|  |  |  |- app.js
|  |  |  |- index.html
|  |  |  |- README.md
|  |  |  `- styles.css
|  |  |- 05671906-7b6d-47eb-95f5-ad1ed40411bc
|  |  |  |- src
|  |  |  |  |- index.js
|  |  |  |  |- main.jsx
|  |  |  |  `- styles.css
|  |  |  |- index.html
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 13be2afa-ef2b-4cca-acfc-eafac0c5840c
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 1da62a18-3833-409e-9400-f96420de48b2
|  |  |  `- vite.config.js
|  |  |- 30e4c64c-b4f2-4a1c-b871-79674f18aff8
|  |  |  |- src
|  |  |  |  |- App.js
|  |  |  |  |- App.jsx
|  |  |  |  |- index.js
|  |  |  |  |- main.jsx
|  |  |  |  `- styles.css
|  |  |  |- index.html
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 3891ca8b-3dc6-47db-9af5-05a96c3814da
|  |  |  |- src
|  |  |  |  |- App.js
|  |  |  |  |- App.jsx
|  |  |  |  |- index.css
|  |  |  |  |- index.js
|  |  |  |  |- main.jsx
|  |  |  |  `- styles.css
|  |  |  |- index.html
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 4118eb78-5ce5-4b1c-8415-57198c1d2707
|  |  |  |- src
|  |  |  |  |- App.js
|  |  |  |  |- App.jsx
|  |  |  |  |- index.css
|  |  |  |  |- index.js
|  |  |  |  |- main.jsx
|  |  |  |  `- styles.css
|  |  |  |- index.html
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 52cbd897-9516-4268-99fe-8d39bf427248
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 5660eaf5-d9e6-45f8-a2e3-6b4dc4033085
|  |  |  |- index.html
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 7540cda4-0444-44ce-a382-74eb2c9938b3
|  |  |  |- src
|  |  |  |  |- App.js
|  |  |  |  |- App.jsx
|  |  |  |  |- index.css
|  |  |  |  |- index.js
|  |  |  |  |- main.jsx
|  |  |  |  `- styles.css
|  |  |  |- index.html
|  |  |  |- package.json
|  |  |  |- README.md
|  |  |  `- vite.config.js
|  |  |- 7b144d56-0c3b-48fb-b430-58ec212f82c0
|  |  |  |- backend
|  |  |  |  |- main.py
|  |  |  |  `- requirements.txt
|  |  |  |- frontend
|  |  |  |  |- src
|  |  |  |  |  |- App.js
|  |  |  |  |  `- index.js
|  |  |  |  |- package.json
|  |  |  |  `- tailwind.config.js
|  |  |  |- src
|  |  |  |  |- App.jsx
|  |  |  |  |- main.jsx
|  |  |  |  `- styles.css
|  |  |  |- index.html
|  |  |  |-