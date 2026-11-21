using './main.bicep'

// Example parameters. The Postgres password is read from the environment at deploy time:
//   export PG_ADMIN_PASSWORD=...; az deployment group create -g <rg> -p deploy/azure/main.bicepparam
param prefix = 'receptly'
param imageTag = '0.1.0'
param registry = 'ghcr.io/hamza533'
param allowedOrigins = 'https://receptly.example.com'
param postgresAdminPassword = readEnvironmentVariable('PG_ADMIN_PASSWORD', '')
