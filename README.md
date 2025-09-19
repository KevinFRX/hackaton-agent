# MeetToTask - Google Docs Monitoring System

A comprehensive Python API system for monitoring Google Docs changes with real-time notifications via Slack, email, and webhooks.

## 🚀 Features

### 📄 Google Docs Integration
- **Service Account Authentication** - Secure access using Google Service Account
- **Document Reading** - Read and parse Google Docs content
- **Change Detection** - Real-time monitoring of document modifications
- **Folder Monitoring** - Monitor entire folders for new documents

### 🔔 Notification System
- **Slack Integration** - Real-time notifications to Slack channels
- **Email Notifications** - SMTP-based email alerts
- **Webhook Support** - Custom webhook endpoints for notifications
- **Multiple Channels** - Send notifications to multiple destinations simultaneously

### 🔍 Monitoring Capabilities
- **Webhook-based Detection** - Real-time change detection using Google Drive webhooks
- **Polling System** - Periodic checking with configurable intervals
- **Folder Discovery** - Automatic detection of new documents in monitored folders
- **Change History** - Complete audit trail of all document changes

### 🤖 AI Integration
- **Google ADK Integration** - AI-powered document processing
- **Gemini 2.5 Pro** - Advanced document analysis and processing
- **Meeting Notes Processing** - Automatic extraction and processing of meeting notes

## 📋 API Endpoints

### Authentication
- `GET /api/auth/status` - Check authentication status
- `POST /api/auth/init` - Initialize authentication

### Document Management
- `GET /api/docs` - List available documents
- `GET /api/docs/{document_id}` - Get specific document content

### Change Detection
- `POST /api/changes/init` - Initialize change detection services
- `GET /api/changes/check/{document_id}` - Check for changes in specific document
- `GET /api/changes/history` - Get change history

### Webhook Management
- `POST /api/changes/webhook/setup` - Setup webhook for document
- `DELETE /api/changes/webhook/{document_id}` - Remove webhook
- `GET /api/changes/webhooks` - List active webhooks
- `POST /api/changes/webhook/receive` - Receive webhook notifications

### Polling System
- `POST /api/changes/polling/add` - Add document to polling
- `DELETE /api/changes/polling/{document_id}` - Remove document from polling
- `GET /api/changes/polling/status` - Get polling status
- `GET /api/changes/polling/documents` - List documents in polling

### Folder Monitoring
- `POST /api/changes/folder/webhook/setup` - Setup folder webhook
- `DELETE /api/changes/folder/webhook/{folder_id}` - Remove folder webhook
- `GET /api/changes/folder/webhooks` - List folder webhooks
- `POST /api/changes/folder/polling/add` - Add folder to polling
- `DELETE /api/changes/folder/polling/{folder_id}` - Remove folder from polling
- `GET /api/changes/folder/check/{folder_id}` - Check folder for new documents
- `GET /api/changes/folder/documents/{folder_id}` - List documents in folder

### Notifications
- `GET /api/notifications/history` - Get notification history
- `GET /api/notifications/stats` - Get notification statistics
- `POST /api/notifications/webhook/add` - Add notification webhook endpoint

### AI Agent
- `POST /api/agent/process-meeting-notes` - Process meeting notes with AI
- `POST /api/agent/process-document` - Process document with AI

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Google Cloud Project with Google Docs API enabled
- Google Service Account with appropriate permissions
- Slack App with Bot Token (optional)
- SMTP server for email notifications (optional)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd MeetToTask
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Setup Google Service Account**
   - Create a Service Account in Google Cloud Console
   - Download the JSON key file
   - Place it as `service-account-key.json` in the project root
   - Update `GOOGLE_SERVICE_ACCOUNT_PATH` in `.env`

5. **Configure Slack (optional)**
   - Create a Slack App at https://api.slack.com/apps
   - Get Bot Token (starts with `xoxb-`)
   - Get Channel ID from Slack
   - Update `SLACK_API_TOKEN` and `SLACK_CHANNEL_ID` in `.env`

6. **Run the application**
   ```bash
   python3 main_integrated.py
   ```

## ⚙️ Configuration

### Environment Variables

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account-key.json

# Slack Configuration
SLACK_API_TOKEN=xoxb-your-bot-token
SLACK_CHANNEL_ID=C1234567890

# Email Configuration (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com

# Change Detection Configuration
WEBHOOK_BASE_URL=http://localhost:8000
NOTIFICATION_EMAIL=your-email@domain.com

# Folder Configuration
FOLDER_ID=your-google-drive-folder-id
```

## 🧪 Usage Examples

### Monitor a Document
```bash
# Add document to polling
curl -X POST "http://localhost:8000/api/changes/polling/add?document_id=DOC_ID&interval_seconds=300"

# Check for changes manually
curl "http://localhost:8000/api/changes/check/DOC_ID"
```

### Monitor a Folder
```bash
# Add folder to polling
curl -X POST "http://localhost:8000/api/changes/folder/polling/add?folder_id=FOLDER_ID&interval_seconds=300"

# Check folder for new documents
curl "http://localhost:8000/api/changes/folder/check/FOLDER_ID"
```

### Setup Webhook
```bash
# Setup webhook for real-time notifications
curl -X POST "http://localhost:8000/api/changes/webhook/setup?document_id=DOC_ID&webhook_url=https://your-app.com/webhook"
```

## 📊 Monitoring

### Check System Status
```bash
# Get polling status
curl "http://localhost:8000/api/changes/polling/status"

# Get notification statistics
curl "http://localhost:8000/api/notifications/stats"

# Get change history
curl "http://localhost:8000/api/changes/history"
```

## 🔧 Architecture

### Services
- **AuthService** - Google authentication management
- **DocsService** - Google Docs API integration
- **ChangeDetectionService** - Change detection and webhook management
- **NotificationService** - Multi-channel notification system
- **PollingService** - Automated polling and monitoring

### Key Features
- **Async/Await** - Full async support for high performance
- **Error Handling** - Comprehensive error handling and logging
- **Configurable Intervals** - Customizable polling intervals
- **Multi-channel Notifications** - Slack, email, and webhook support
- **Change History** - Complete audit trail
- **Service Account Auth** - Secure authentication without user interaction

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For support and questions, please open an issue in the repository.