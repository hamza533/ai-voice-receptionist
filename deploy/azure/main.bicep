// Production profile for a client: Azure Container Apps (API, worker, voice agent),
// PostgreSQL Flexible Server, Blob Storage, Key Vault, managed identity, Application
// Insights. Validated in CI (`az bicep build`); deployed only by the disabled-by-default
// workflow in .github/workflows/deploy-azure.yml.
//
// Secrets are never passed as app settings: Key Vault holds them and the container apps
// read them through a user-assigned managed identity.

targetScope = 'resourceGroup'

@description('Short name used as a prefix for every resource.')
@minLength(3)
@maxLength(12)
param prefix string = 'receptly'

param location string = resourceGroup().location

@description('Container image tag (semantic version), e.g. 0.1.0')
param imageTag string

@description('Registry hosting the images, e.g. ghcr.io/<owner>')
param registry string = 'ghcr.io/hamza533'

@description('Postgres administrator login (password comes from Key Vault).')
param postgresAdminLogin string = 'receptionist'

@secure()
@description('Postgres administrator password. Also stored in Key Vault as database-url.')
param postgresAdminPassword string

@description('Allowed browser origins for the API (the dashboard URL).')
param allowedOrigins string

@description('Business mobile/landline to transfer callers to (SIP transfer).')
param handoffNumber string = ''

param apiMinReplicas int = 1
param apiMaxReplicas int = 5

var tags = { app: 'ai-voice-receptionist', managedBy: 'bicep' }
var kvName = '${prefix}-kv-${uniqueString(resourceGroup().id)}'
var storageName = toLower('${prefix}st${uniqueString(resourceGroup().id)}')
var pgName = '${prefix}-pg-${uniqueString(resourceGroup().id)}'

// ---------------------------------------------------------------- observability

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-insights'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

// ---------------------------------------------------------------- identity & secrets

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-identity'
  location: location
  tags: tags
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take(kvName, 24)
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
  }
}

// "Key Vault Secrets User" for the app identity.
resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, 'kv-secrets-user')
  scope: vault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource dbSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'database-url'
  properties: {
    value: 'postgresql+psycopg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/receptionist?sslmode=require'
  }
}

// Other secrets (livekit-api-key, livekit-api-secret, gemini-api-key, session-secret,
// agent-service-token, google-service-account-json, smtp-password) are set once by the
// operator: `az keyvault secret set --vault-name <kv> --name <name> --value <value>`.
var vaultUri = 'https://${vault.name}${environment().suffixes.keyvaultDns}/'

var secretNames = [
  'session-secret'
  'agent-service-token'
  'livekit-url'
  'livekit-api-key'
  'livekit-api-secret'
  'gemini-api-key'
  'google-service-account-json'
  'google-calendar-id'
  'smtp-host'
  'smtp-user'
  'smtp-password'
]

var kvRefs = [for name in secretNames: {
  name: name
  keyVaultUrl: '${vaultUri}secrets/${name}'
  identity: identity.id
}]

// ---------------------------------------------------------------- data

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: pgName
  location: location
  tags: tags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32, autoGrow: 'Enabled' }
    backup: { backupRetentionDays: 14, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    authConfig: { activeDirectoryAuth: 'Disabled', passwordAuth: 'Enabled' }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'receptionist'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'allow-azure-services'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take(storageName, 24)
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

// Reserved for optional call recordings (off by default; needs consent + retention rules).
resource recordings 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'recordings'
  properties: { publicAccess: 'None' }
}

resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, 'blob-contributor')
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

// ---------------------------------------------------------------- container apps

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var commonEnv = [
  { name: 'ENVIRONMENT', value: 'production' }
  { name: 'DEMO_MODE', value: 'false' }
  { name: 'COOKIE_SECURE', value: 'true' }
  { name: 'WORKER_MODE', value: 'separate' }
  { name: 'ALLOWED_ORIGINS', value: allowedOrigins }
  { name: 'HANDOFF_NUMBER', value: handoffNumber }
  { name: 'TRANSFER_ENABLED', value: empty(handoffNumber) ? 'false' : 'true' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'SESSION_SECRET', secretRef: 'session-secret' }
  { name: 'AGENT_SERVICE_TOKEN', secretRef: 'agent-service-token' }
  { name: 'LIVEKIT_URL', secretRef: 'livekit-url' }
  { name: 'LIVEKIT_API_KEY', secretRef: 'livekit-api-key' }
  { name: 'LIVEKIT_API_SECRET', secretRef: 'livekit-api-secret' }
  { name: 'GEMINI_API_KEY', secretRef: 'gemini-api-key' }
  { name: 'GOOGLE_SERVICE_ACCOUNT_JSON', secretRef: 'google-service-account-json' }
  { name: 'GOOGLE_CALENDAR_ID', secretRef: 'google-calendar-id' }
  { name: 'SMTP_HOST', secretRef: 'smtp-host' }
  { name: 'SMTP_USER', secretRef: 'smtp-user' }
  { name: 'SMTP_PASSWORD', secretRef: 'smtp-password' }
]

var secrets = concat(kvRefs, [
  {
    name: 'database-url'
    keyVaultUrl: '${vaultUri}secrets/database-url'
    identity: identity.id
  }
])

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-api'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  dependsOn: [kvSecretsUser, dbSecret]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      secrets: secrets
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: split(allowedOrigins, ',')
          allowCredentials: true
        }
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${registry}/ai-voice-receptionist-api:${imageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: commonEnv
          probes: [
            { type: 'Liveness', httpGet: { path: '/health', port: 8000 }, periodSeconds: 15 }
            { type: 'Readiness', httpGet: { path: '/ready', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '50' } } }]
      }
    }
  }
}

resource worker 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-worker'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  dependsOn: [kvSecretsUser, dbSecret]
  properties: {
    managedEnvironmentId: env.id
    configuration: { secrets: secrets }
    template: {
      // 30 s grace period: in-flight jobs finish or are released back to the queue.
      terminationGracePeriodSeconds: 30
      containers: [
        {
          name: 'worker'
          image: '${registry}/ai-voice-receptionist-api:${imageTag}'
          command: ['python', '-m', 'app.jobs.worker']
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: commonEnv
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}

resource agent 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-agent'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  dependsOn: [kvSecretsUser]
  properties: {
    managedEnvironmentId: env.id
    configuration: { secrets: kvRefs }
    template: {
      terminationGracePeriodSeconds: 600 // let live calls finish on deploy
      containers: [
        {
          name: 'agent'
          image: '${registry}/ai-voice-receptionist-agent:${imageTag}'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'API_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }
            { name: 'AGENT_SERVICE_TOKEN', secretRef: 'agent-service-token' }
            { name: 'LIVEKIT_URL', secretRef: 'livekit-url' }
            { name: 'LIVEKIT_API_KEY', secretRef: 'livekit-api-key' }
            { name: 'LIVEKIT_API_SECRET', secretRef: 'livekit-api-secret' }
            { name: 'GOOGLE_API_KEY', secretRef: 'gemini-api-key' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 4 }
    }
  }
}

output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output keyVaultName string = vault.name
output postgresHost string = postgres.properties.fullyQualifiedDomainName
