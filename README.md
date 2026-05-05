# Security Copilot for MSSP — CISO Monthly Report Automation

MSSP（マネージドセキュリティサービスプロバイダー）が顧客の CISO 向けに月次セキュリティレポートを**完全自動**で生成するシステムです。

## アーキテクチャ

```
MSSP テナント                          顧客テナント
┌─────────────────────────┐           ┌──────────────────┐
│  Logic App              │           │  Sentinel        │
│   ├─ KQL 実行 ──────────┼───────────┼→ Workspace       │
│   ├─ AI 分析            │ Lighthouse│                  │
│   │   └─ Security       │           └──────────────────┘
│   │      Copilot (SCU)  │
│   └─ HTML レポート生成  │
└─────────────────────────┘
```

## コンポーネント

| フォルダ | 内容 | 説明 |
|---|---|---|
| `logic-app/` | ARM テンプレート | Logic App のデプロイ定義（日本語版 v5 / 英語版 v4） |
| `azure-function/` | Python Function App | Sentinel KQL プロキシ（Lighthouse クロステナント対応） |
| `lighthouse/` | ARM テンプレート | Azure Lighthouse 委任設定 |
| `docs/` | サンプルレポート | 実際の出力例 |

## セットアップ手順

### 前提条件

- Azure サブスクリプション（MSSP テナント）
- Security Copilot SCU（最低1ユニット）
- Azure CLI (`az`) インストール済み
- 顧客テナントの管理者の協力（Lighthouse 委任用）

### Step 1: Azure Function のデプロイ

```bash
# Function App を作成
az functionapp create \
  --resource-group <your-rg> \
  --name <function-name> \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type linux \
  --storage-account <storage-name> \
  --assign-identity [system]

# コードをデプロイ
cd azure-function
func azure functionapp publish <function-name>
```

### Step 2: Lighthouse 委任の設定

顧客テナントのサブスクリプションスコープで Lighthouse テンプレートをデプロイします（顧客テナントの管理者が実行）。

```bash
az deployment sub create \
  --location eastus \
  --template-file lighthouse/lighthouse_delegation.json \
  --parameters \
    managedByTenantId="<mssp-tenant-id>" \
    principalId="<function-app-mi-object-id>" \
    registrationDefinitionGuid="$(uuidgen)" \
    registrationAssignmentGuid="$(uuidgen)"
```

### Step 3: Logic App のデプロイ

```bash
az deployment group create \
  --resource-group <your-rg> \
  --template-file logic-app/ciso-report-logicapp-v5-ja.json \
  --parameters \
    customerSubscriptionId="<customer-sub-id>" \
    customerResourceGroup="<customer-rg>" \
    customerWorkspaceName="<customer-workspace>"
```

### Step 4: Security Copilot API Connection の OAuth 承認

Azure ポータルで API Connection リソースを開き、「承認」ボタンをクリックして OAuth サインインを完了します。

### Step 5: 動作確認

Logic App の手動トリガーでレポートが生成されることを確認します。

## レポート出力（5セクション）

1. **エグゼクティブサマリー** — AI によるセキュリティ態勢の要約
2. **月次インシデントサマリー** — インシデント件数 + 高重大度一覧
3. **脅威ランドスケープ** — 脅威アクター・TTP 分析
4. **トップアラート** — 発生頻度 Top 10
5. **推奨アクション** — インシデントごとの具体的対策

## ファイル一覧

| ファイル | 説明 |
|---|---|
| `logic-app/ciso-report-logicapp-v5-ja.json` | Logic App ARM テンプレート（日本語版、本番用） |
| `logic-app/ciso-report-logicapp-v4-en.json` | Logic App ARM テンプレート（英語版） |
| `azure-function/function_app.py` | KQL プロキシ Function App |
| `azure-function/host.json` | Function App ホスト設定 |
| `azure-function/requirements.txt` | Python 依存パッケージ |
| `lighthouse/lighthouse_delegation.json` | Lighthouse 委任 ARM テンプレート |
| `docs/sample-report-v5.html` | サンプルレポート出力（日本語版） |

## ライセンス

MIT License
Security Copilot for MSSP - CISO Monthly Report Automation (Logic App + Azure Function + Lighthouse)
