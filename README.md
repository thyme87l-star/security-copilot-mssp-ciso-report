# Security Copilot for MSSP — CISO Monthly Report Automation

MSSP（マネージドセキュリティサービスプロバイダー）が顧客の CISO 向けに月次セキュリティレポートを**完全自動**で生成するシステムです。

## アーキテクチャ

```
MSSP テナント                          顧客テナント
┌─────────────────────────┐           ┌──────────────────┐
│  Logic App              │           │  Sentinel        │
│  (Managed Identity)     │ Lighthouse│  Workspace       │
│   ├─ MI+Lighthouse ─────┼───────────┼→ KQL クエリ      │
│   │   (ARM Query API)   │           │  (読取のみ)      │
│   ├─ OAuth API ─────────┼──┐        └──────────────────┘
│   │                     │  │ Security Copilot
│   └─ HTML レポート生成  │  └→ AI 分析・サマリー
└─────────────────────────┘
```

**ポイント:** Logic App が ARM Query API を直接呼び出します（Azure Function 等の中間プロキシは不要）。Lighthouse 委任先は Logic App の Managed Identity です。

## コンポーネント

| フォルダ | 内容 | 説明 |
|---|---|---|
| `logic-app/` | ARM テンプレート | Logic App のデプロイ定義（日本語版 v5 / 英語版 v4） |
| `lighthouse/` | ARM テンプレート | Azure Lighthouse 委任設定（Log Analytics Reader） |
| `docs/` | サンプルレポート | 実際の出力例 |

## セットアップ手順

### 前提条件

- Azure サブスクリプション（MSSP テナント）
- Security Copilot SCU（最低1ユニット）
- Azure ポータル + Cloud Shell（ローカルツールのインストール不要）
- 顧客テナントの管理者の協力（Lighthouse 委任用）

### Step 1: Logic App のデプロイ

MSSP テナントの Cloud Shell（Bash）で実行します。

```bash
# リポジトリを取得
git clone https://github.com/thyme87l-star/security-copilot-mssp-ciso-report.git
cd security-copilot-mssp-ciso-report

# リソースグループを作成
az group create --name MSSP-CISO-RG --location eastus

# Logic App をデプロイ
az deployment group create \
  --resource-group MSSP-CISO-RG \
  --template-file logic-app/ciso-report-logicapp-v5-ja.json \
  --parameters \
    customerWorkspaceId="<顧客ワークスペースID(GUID)>" \
    customerSubscriptionId="<顧客サブスクリプションID>" \
    customerResourceGroup="<顧客リソースグループ名>" \
    customerWorkspaceName="<顧客ワークスペース名>"

# Logic App MI の principalId を取得（Step 2 で使用）
az deployment group show \
  --resource-group MSSP-CISO-RG \
  --name ciso-report-logicapp-v5-ja \
  --query "properties.outputs.logicAppPrincipalId.value" -o tsv
```

### Step 2: Lighthouse 委任の設定

顧客テナントの管理者が Cloud Shell（Bash）で実行します。

```bash
git clone https://github.com/thyme87l-star/security-copilot-mssp-ciso-report.git
cd security-copilot-mssp-ciso-report

REG_DEF_GUID=$(uuidgen)
REG_ASSIGN_GUID=$(uuidgen)

az deployment sub create \
  --location eastus \
  --template-file lighthouse/lighthouse_delegation.json \
  --parameters \
    managedByTenantId="<MSSPテナントID>" \
    principalId="<Step 1 で取得した Logic App MI principalId>" \
    registrationDefinitionGuid="$REG_DEF_GUID" \
    registrationAssignmentGuid="$REG_ASSIGN_GUID"
```

### Step 3: Security Copilot API Connection の OAuth 承認

Azure ポータルで API Connection リソース（`securitycopilot-connection`）を開き、「承認」ボタンをクリックして OAuth サインインを完了します。

### Step 4: 動作確認

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
| `lighthouse/lighthouse_delegation.json` | Lighthouse 委任 ARM テンプレート |
| `docs/sample-report-v5.html` | サンプルレポート出力（日本語版） |

## ライセンス

MIT License
Security Copilot for MSSP - CISO Monthly Report Automation (Logic App + Lighthouse)
