<template>
  <v-app>
    <div class="notebook-layout">
    <!-- Header -->
    <div class="notebook-header">
      <div class="header-left">
        <LayoutAppLogoDesktop style="height: 32px; margin-right: 12px" />
      </div>
      <div class="header-right">
        <v-btn variant="text" size="small" class="header-btn">+ Create Workspace</v-btn>
        <v-btn icon variant="text" size="small">
          <v-icon>mdi-share-variant</v-icon>
        </v-btn>
        <v-btn icon variant="text" size="small">
          <v-icon>mdi-cog</v-icon>
        </v-btn>
        <v-btn icon variant="text" size="small">
          <v-icon>mdi-dots-grid</v-icon>
        </v-btn>
        <v-avatar size="32" color="primary">
          <span class="text-white">Mr</span>
        </v-avatar>
      </div>
    </div>

    <!-- Three-Panel Layout -->
    <div class="panel-container">
      <!-- Left Panel: Sources -->
      <div 
        class="panel panel-left" 
        :class="{ 'collapsed': leftCollapsed }"
        :style="{ width: leftCollapsed ? '60px' : '25%' }"
      >
        <div v-if="!leftCollapsed">
          <div class="panel-header">
            <span class="panel-title">Sources</span>
            <div class="panel-toggle-icon" @click="leftCollapsed = true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="2" width="12" height="12" stroke="currentColor" stroke-width="1" fill="none" rx="1"/>
                <line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1"/>
              </svg>
            </div>
          </div>
          
          <div 
            class="upload-zone"
            :class="{ 'drag-over': isDragOver, 'uploading': isUploading }"
            @drop="handleDrop"
            @dragover.prevent="isDragOver = true"
            @dragleave="isDragOver = false"
            @dragenter.prevent
            @click="triggerFileInput"
          >
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept=".xlsx,.xls,.docx,.doc,.pdf,.txt"
              @change="handleFileSelect"
              class="file-input-hidden"
            />
            <div class="upload-content">
              <v-icon size="48" class="upload-icon-large">mdi-cloud-upload</v-icon>
              <p class="upload-text">{{ isUploading ? 'Uploading...' : 'Drag & drop files here' }}</p>
              <p class="upload-subtext">{{ isUploading ? 'Please wait' : 'or click to browse' }}</p>
              <p class="upload-hint">Excel, Word, PDF, or Text files</p>
            </div>
          </div>
          
          <div class="sources-list">
            <div v-if="sources.length === 0" class="empty-state">
              <p>No documents uploaded. Upload Excel, Word, PDF, or text files to process.</p>
            </div>
            <div v-for="source in sources" :key="source.id" class="source-item">
              <div class="source-info">
                <v-icon size="16" class="mr-2">{{ getFileIcon(source.type) }}</v-icon>
                <div>
                  <span class="source-name">{{ source.name }}</span>
                  <span class="source-type">{{ source.type }}</span>
                </div>
              </div>
              <v-btn icon size="x-small" variant="text" @click="removeSource(source.id)">
                <v-icon size="16">mdi-close</v-icon>
              </v-btn>
            </div>
          </div>
        </div>
        <div v-else class="panel-collapsed-content">
          <v-btn icon variant="text" @click="leftCollapsed = false">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </div>
      </div>


      <!-- Center Panel: Chat -->
      <div class="panel panel-center">
        <div class="panel-header">
          <span class="panel-title">Chat</span>
        </div>

        <div class="chat-content">
          <div v-if="chatHistory.length === 0" class="empty-chat">
            <div class="upload-icon"></div>
            <h3>Start chatting with SparksBM Agent</h3>
            <p class="text-caption">Upload documents or ask questions</p>
          </div>
          
          <div v-else class="messages">
            <div 
              v-for="(msg, idx) in chatHistory" 
              :key="idx" 
              class="message"
              :class="msg.role"
            >
              <span v-if="msg.role === 'assistant'" class="agent-label">Agent:</span>
              <div v-if="msg.isTable" class="table-container">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th v-for="col in msg.tableColumns" :key="col">{{ col }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, rowIdx) in msg.tableData" :key="rowIdx">
                      <td v-for="col in msg.tableColumns" :key="col">
                        {{ row[col.toLowerCase()] || row[col] || '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div v-if="msg.tableTotal && msg.tableData && msg.tableTotal > msg.tableData.length" class="table-footer">
                  ... and {{ msg.tableTotal - msg.tableData.length }} more
                </div>
              </div>
              <div v-else class="message-text" v-html="formatMessage(msg.content)"></div>
            </div>
          </div>
        </div>

        <div class="chat-input-container">
          <v-text-field
            v-model="currentMessage"
            placeholder="Type your message..."
            variant="outlined"
            density="compact"
            hide-details
            @keyup.enter="sendMessage"
          />
          <v-btn icon @click="sendMessage">
            <v-icon>mdi-send</v-icon>
          </v-btn>
        </div>
      </div>


      <!-- Right Panel: Studio -->
      <div 
        class="panel panel-right"
        :class="{ 'collapsed': rightCollapsed }"
        :style="{ width: rightCollapsed ? '60px' : '30%' }"
      >
        <div v-if="!rightCollapsed">
          <div class="panel-header">
            <span class="panel-title">Studio</span>
            <div class="panel-toggle-icon" @click="rightCollapsed = true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="2" width="12" height="12" stroke="currentColor" stroke-width="1" fill="none" rx="1"/>
                <line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1"/>
              </svg>
            </div>
          </div>

          <!-- Document Processing Menu -->
          <div class="studio-section">
            <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.document = !collapsedCategories.document">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.document ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-file-document</v-icon>
                  Document Processing
                </div>
              <div v-show="!collapsedCategories.document" class="menu-items">
                <div class="menu-item clickable" @click="() => analyzeDocument('excel')">
                  <v-icon size="18" class="mr-2">mdi-file-excel</v-icon>
                  <span>Analyze Excel File</span>
                    </div>
                <div class="menu-item clickable" @click="() => analyzeDocument('word')">
                  <v-icon size="18" class="mr-2">mdi-file-word</v-icon>
                  <span>Analyze Word Document</span>
                  </div>
                <div class="menu-item clickable" @click="() => analyzeDocument('pdf')">
                  <v-icon size="18" class="mr-2">mdi-file-pdf-box</v-icon>
                  <span>Analyze PDF File</span>
                </div>
              </div>
                </div>
              </div>

          <v-divider class="my-4" />

          <!-- ISMS OPERATIONS Menu -->
          <div class="studio-section">
            <div class="menu-category">
              <div class="category-title clickable" @click="collapsedCategories.ismsNav = !collapsedCategories.ismsNav">
                <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsNav ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                <v-icon size="16" class="mr-1">mdi-view-grid</v-icon>
                ISMS OPERATIONS
                </div>
              <div v-show="!collapsedCategories.ismsNav" class="isms-menu">
              
              <!-- Scopes Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsScopes = !collapsedCategories.ismsScopes">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsScopes ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-grid</v-icon>
                  Scopes
                </div>
                <div v-show="!collapsedCategories.ismsScopes" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('create scope')">
                    <v-icon size="18" class="mr-2">mdi-plus-circle</v-icon>
                    <span>Create</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('list scopes')">
                    <v-icon size="18" class="mr-2">mdi-format-list-bulleted</v-icon>
                    <span>List</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('get scope')">
                    <v-icon size="18" class="mr-2">mdi-eye</v-icon>
                    <span>Get</span>
                  </div>
                </div>
              </div>

              <v-divider class="my-1" />

              <!-- Assets Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsAssets = !collapsedCategories.ismsAssets">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsAssets ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-server</v-icon>
                  Assets
                </div>
                <div v-show="!collapsedCategories.ismsAssets" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('create asset')">
                    <v-icon size="18" class="mr-2">mdi-plus-circle</v-icon>
                    <span>Create</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('list assets')">
                    <v-icon size="18" class="mr-2">mdi-format-list-bulleted</v-icon>
                    <span>List</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('get asset')">
                    <v-icon size="18" class="mr-2">mdi-eye</v-icon>
                    <span>Get</span>
                  </div>
                </div>
              </div>

              <v-divider class="my-1" />

              <!-- Persons Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsPersons = !collapsedCategories.ismsPersons">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsPersons ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-account</v-icon>
                  Persons
                </div>
                <div v-show="!collapsedCategories.ismsPersons" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('create person')">
                    <v-icon size="18" class="mr-2">mdi-plus-circle</v-icon>
                    <span>Create</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('list persons')">
                    <v-icon size="18" class="mr-2">mdi-format-list-bulleted</v-icon>
                    <span>List</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('get person')">
                    <v-icon size="18" class="mr-2">mdi-eye</v-icon>
                    <span>Get</span>
                  </div>
                </div>
              </div>

              <v-divider class="my-1" />

              <!-- Processes Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsProcesses = !collapsedCategories.ismsProcesses">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsProcesses ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-database-cog</v-icon>
                  Processes
                </div>
                <div v-show="!collapsedCategories.ismsProcesses" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('create process')">
                    <v-icon size="18" class="mr-2">mdi-plus-circle</v-icon>
                    <span>Create</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('list processes')">
                    <v-icon size="18" class="mr-2">mdi-format-list-bulleted</v-icon>
                    <span>List</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('get process')">
                    <v-icon size="18" class="mr-2">mdi-eye</v-icon>
                    <span>Get</span>
                  </div>
                </div>
              </div>

              <v-divider class="my-1" />

              <!-- Controls Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsControls = !collapsedCategories.ismsControls">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsControls ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-shield-check</v-icon>
                  Controls
                </div>
                <div v-show="!collapsedCategories.ismsControls" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('create control')">
                    <v-icon size="18" class="mr-2">mdi-plus-circle</v-icon>
                    <span>Create</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('list controls')">
                    <v-icon size="18" class="mr-2">mdi-format-list-bulleted</v-icon>
                    <span>List</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('get control')">
                    <v-icon size="18" class="mr-2">mdi-eye</v-icon>
                    <span>Get</span>
                  </div>
                </div>
              </div>

              <v-divider class="my-1" />

              <!-- Documents Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsDocuments = !collapsedCategories.ismsDocuments">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsDocuments ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                  <v-icon size="16" class="mr-1">mdi-file-document</v-icon>
                  Documents
                </div>
                <div v-show="!collapsedCategories.ismsDocuments" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('create document')">
                    <v-icon size="18" class="mr-2">mdi-plus-circle</v-icon>
                    <span>Create</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('list documents')">
                    <v-icon size="18" class="mr-2">mdi-format-list-bulleted</v-icon>
                    <span>List</span>
                  </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('get document')">
                    <v-icon size="18" class="mr-2">mdi-eye</v-icon>
                    <span>Get</span>
                  </div>
                </div>
              </div>

              <v-divider class="my-2" />

              <!-- Reports Section -->
              <div class="menu-category">
                <div class="category-title clickable" @click="collapsedCategories.ismsReports = !collapsedCategories.ismsReports">
                  <v-icon size="16" class="mr-1">{{ collapsedCategories.ismsReports ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                      <v-icon size="16" class="mr-1">mdi-chart-bar</v-icon>
                      Reports
                    </div>
                <div v-show="!collapsedCategories.ismsReports" class="menu-items">
                  <div class="menu-item clickable" @click="sendMenuMessage('generate inventory of assets report')">
                    <v-icon size="18" class="mr-2">mdi-file-chart</v-icon>
                    <span>Inventory of Assets</span>
                        </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('generate statement of applicability report')">
                    <v-icon size="18" class="mr-2">mdi-file-check</v-icon>
                    <span>Statement of Applicability</span>
                      </div>
                  <div class="menu-item clickable" @click="sendMenuMessage('generate risk assessment report')">
                    <v-icon size="18" class="mr-2">mdi-chart-line</v-icon>
                    <span>Risk Assessment</span>
                        </div>
                      </div>
                    </div>
                  </div>
            </div>
          </div>

          <v-divider class="my-4" />

          <div class="studio-section">
            <h4 class="section-title">Agent Status:</h4>
            <div class="agent-status">
              <v-chip color="success" size="small">SparksBM Agent Ready</v-chip>
            </div>
          </div>
        </div>
        <div v-else class="panel-collapsed-content">
          <v-btn icon variant="text" @click="rightCollapsed = false">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </div>
      </div>
    </div>


    <!-- Footer -->
    <div class="notebook-footer">
      SparksBM Agent can be inaccurate; please double check its responses.
    </div>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import LayoutAppLogoDesktop from '~/components/layout/AppLogoDesktop.vue'

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const sources = ref<Array<{id: string, name: string, type: string}>>([])
const chatHistory = ref<Array<{
  role: string
  content: string
  isTable?: boolean
  tableColumns?: string[]
  tableData?: any[]
  tableTotal?: number
}>>([])

const formatMessage = (text: string): string => {
  // Convert markdown-style formatting to HTML
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}
const currentMessage = ref('')
const sessionId = ref<string | null>(null)
const isDragOver = ref(false)
const isUploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// Collapsed state for categories
const collapsedCategories = ref({
  document: true,
  ismsNav: true,
  ismsScopes: true,
  ismsAssets: true,
  ismsPersons: true,
  ismsProcesses: true,
  ismsControls: true,
  ismsDocuments: true,
  ismsReports: true
})

const config = useRuntimeConfig()
const API_BASE = config.public.apiBase as string

const createSession = async (): Promise<string | null> => {
  try {
    const response = await $fetch<{ sessionId: string }>(`${API_BASE}/api/agent/session`, {
      method: 'POST',
      params: { userId: 'default' }
    })
    sessionId.value = response.sessionId
    return response.sessionId
  } catch (e) {
    console.error('Failed to create session:', e)
    return null
  }
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const analyzeDocument = async (fileType: 'excel' | 'word' | 'pdf') => {
  // Check if there's an uploaded file of the matching type
  const matchingSource = sources.value.find(source => {
    const sourceType = source.type.toLowerCase()
    if (fileType === 'excel') {
      return sourceType === 'excel'
    } else if (fileType === 'word') {
      return sourceType === 'word'
    } else if (fileType === 'pdf') {
      return sourceType === 'pdf'
    }
    return false
  })
  
  if (matchingSource) {
    // File already uploaded, analyze it
    const fileTypeName = fileType === 'excel' ? 'Excel' : fileType === 'word' ? 'Word' : 'PDF'
    const analyzeMessage = `Analyze the ${fileTypeName} document "${matchingSource.name}" comprehensively. Provide a detailed, formatted analysis including:
- Document structure and content overview
- Key information and data points
- Important findings or patterns
- Summary and recommendations

Please format the response clearly with sections and bullet points.`
    
    // Add user message
    chatHistory.value.push({
      role: 'user',
      content: analyzeMessage
    })
    
    if (!sessionId.value) {
      await createSession()
}

    try {
      // Send analysis request with the source
      const response = await $fetch<{ 
        status: string
        result?: string | {
          type: 'table' | 'object_detail'
          title?: string
          columns?: string[]
          data?: any[]
          [key: string]: any
        }
        dataType?: 'table' | 'object_detail'
        error?: string 
      }>(`${API_BASE}/api/agent/chat`, {
        method: 'POST',
        body: {
          message: analyzeMessage,
          sources: [matchingSource],
          sessionId: sessionId.value
        }
      })
      
      if (response.status === 'error') {
        chatHistory.value.push({
          role: 'assistant',
          content: `Error: ${response.error || 'Unknown error'}`
        })
      } else {
        let content: string
        if (response.dataType === 'table' && typeof response.result === 'object' && response.result !== null) {
          const tableData = response.result as any
          content = `${tableData.title || 'Analysis'}\n\n`
          if (tableData.columns && tableData.data) {
            content += tableData.columns.join(' | ') + '\n'
            content += tableData.columns.map(() => '---').join(' | ') + '\n'
            tableData.data.slice(0, 10).forEach((row: any) => {
              const values = tableData.columns.map((col: string) => row[col.toLowerCase()] || row[col] || '—')
              content += values.join(' | ') + '\n'
            })
            if (tableData.total && tableData.total > 10) {
              content += `\n... and ${tableData.total - 10} more`
            }
          }
        } else {
          content = typeof response.result === 'string' ? response.result : JSON.stringify(response.result)
        }
        
        chatHistory.value.push({
          role: 'assistant',
          content: content || 'Analysis completed'
        })
      }
    } catch (e: any) {
      chatHistory.value.push({
        role: 'assistant',
        content: `Error: ${e?.message || e?.data?.detail || String(e)}`
      })
    }
  } else {
    // No matching file uploaded, prompt to upload first
    const fileTypeName = fileType === 'excel' ? 'Excel' : fileType === 'word' ? 'Word' : 'PDF'
    chatHistory.value.push({
      role: 'assistant',
      content: `Please upload a ${fileTypeName} file in the Sources panel first, then click "Analyze ${fileTypeName} File" again to analyze it.`
    })
  }
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files) {
    uploadFiles(Array.from(target.files))
    // Reset input so same file can be selected again
    target.value = ''
  }
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragOver.value = false
  
  if (event.dataTransfer?.files) {
    uploadFiles(Array.from(event.dataTransfer.files))
  }
}

const uploadFiles = async (files: File[]) => {
  if (!files || files.length === 0) return
  
  if (!sessionId.value) {
    await createSession()
  }
  
  isUploading.value = true
  
  for (const file of files) {
    const fileType = getFileType(file.name)
    
    // Validate file type
    const allowedExts = ['.xlsx', '.xls', '.docx', '.doc', '.pdf', '.txt']
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase()
    
    if (!allowedExts.includes(fileExt)) {
      chatHistory.value.push({
        role: 'assistant',
        content: `Error: File type ${fileExt} not supported. Allowed: ${allowedExts.join(', ')}`
      })
      continue
    }
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (sessionId.value) {
        formData.append('sessionId', sessionId.value)
      }
      
      const response = await $fetch<{status: string, sourceId?: string, fileName?: string, error?: string}>(
        `${API_BASE}/api/agent/upload`,
        {
          method: 'POST',
          body: formData
        }
      )
      
      if (response.status === 'success' && response.sourceId) {
        sources.value.push({
          id: response.sourceId,
          name: response.fileName || file.name,
          type: fileType
        })
        
        // Show bulk import suggestion if available
        const message = (response as any).message || `✅ Successfully uploaded and processed: ${file.name}`
        chatHistory.value.push({
          role: 'assistant',
          content: message
        })
      } else {
        chatHistory.value.push({
          role: 'assistant',
          content: `❌ Failed to upload ${file.name}: ${response.error || 'Unknown error'}`
        })
      }
    } catch (e: any) {
      chatHistory.value.push({
        role: 'assistant',
        content: `❌ Error uploading ${file.name}: ${e?.message || String(e)}`
      })
    }
  }
  
  isUploading.value = false
}

const getFileType = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase()
  if (['xlsx', 'xls'].includes(ext || '')) return 'excel'
  if (['docx', 'doc'].includes(ext || '')) return 'word'
  if (ext === 'pdf') return 'pdf'
  if (ext === 'txt') return 'text'
  return 'document'
}

const getFileIcon = (type: string): string => {
  if (type === 'excel') return 'mdi-file-excel'
  if (type === 'word') return 'mdi-file-word'
  if (type === 'pdf') return 'mdi-file-pdf-box'
  return 'mdi-file-document'
}

const removeSource = (sourceId: string) => {
  sources.value = sources.value.filter(s => s.id !== sourceId)
}

const sendMenuMessage = async (message: string) => {
  // For menu clicks, use direct ISMS API (bypasses pattern matching)
  // Extract operation and object type from message
  const messageLower = message.toLowerCase().trim()
  
  // Check if it's a direct ISMS operation (list, create, get, etc.)
  const ismsOperations = ['list', 'create', 'get', 'update', 'delete', 'generate']
  const isIsmsOp = ismsOperations.some(op => messageLower.startsWith(op))
  
  // For now, all menu clicks go through regular chat (pattern matching)
  // The direct ISMS API endpoint is available but we'll use chat for simplicity
  
  // Fallback to regular chat (pattern matching)
  currentMessage.value = message
  sendMessage()
}

const sendMessage = async () => {
  if (!currentMessage.value.trim()) return
  
  if (!sessionId.value) {
    const newSessionId = await createSession()
    if (!newSessionId) {
      chatHistory.value.push({
        role: 'assistant',
        content: 'Error: Failed to create session. Please refresh the page.'
      })
      return
    }
  }
  
  const userMsg = currentMessage.value.trim()
  if (!userMsg) return
  
  // Add user message to chat
  chatHistory.value.push({
    role: 'user',
    content: userMsg
  })
  
  // Clear input
  currentMessage.value = ''
  
  try {
    // Get active sources for context
    const activeSources = sources.value.map(s => ({
      id: s.id,
      name: s.name,
      type: s.type,
      domainId: '',
      data: {}
    }))
    
    const response = await $fetch<{ 
      status: string
      result?: string | {
        type: 'table' | 'object_detail'
        title?: string
        columns?: string[]
        data?: any[]
        [key: string]: any
      }
      dataType?: 'table' | 'object_detail'
      error?: string 
    }>(`${API_BASE}/api/agent/chat`, {
      method: 'POST',
      body: {
        message: userMsg,
        sources: activeSources,
        sessionId: sessionId.value
      }
    })
    
    if (response.status === 'error') {
      chatHistory.value.push({
        role: 'assistant',
        content: `Error: ${response.error || 'Unknown error'}`
      })
    } else {
      // Handle structured data (tables) or plain text
      if (response.dataType === 'table' && typeof response.result === 'object' && response.result !== null) {
        // Render as HTML table
        const tableData = response.result as any
      chatHistory.value.push({
        role: 'assistant',
          content: tableData.title || 'Data',
          isTable: true,
          tableColumns: tableData.columns || [],
          tableData: (tableData.data || tableData.items || []).slice(0, 20),
          tableTotal: tableData.total || (tableData.data || tableData.items || []).length
        })
      } else {
        const content = typeof response.result === 'string' ? response.result : JSON.stringify(response.result)
        chatHistory.value.push({
          role: 'assistant',
          content: content || 'No response',
          isTable: false
      })
      }
    }
  } catch (e: any) {
    console.error('Chat error:', e)
    const errorMsg = e?.message || e?.data?.detail || String(e)
    chatHistory.value.push({
      role: 'assistant',
      content: `Error: ${errorMsg}\n\nPlease check:\n1. NotebookLLM API is running (http://localhost:8000)\n2. ISMS backend is running (http://localhost:8070)\n3. Network connection is working`
    })
  }
}

const startResize = (side: 'left' | 'right') => {
  // Resize logic can be added here
}

onMounted(async () => {
  await createSession()
})
</script>

<style scoped>
.notebook-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #0a0a0a;
}

.notebook-header {
  background-color: #1a1a1a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
}

.notebook-title {
  color: #e0e0e0;
  font-size: 1rem;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-btn {
  color: #e0e0e0 !important;
}

.panel-container {
  display: flex;
  height: calc(100vh - 60px - 40px);
  width: 100%;
  padding: 16px;
  padding-bottom: 40px;
  gap: 16px;
  background-color: #1a1a1a;
}

.panel {
  background-color: #212121;
  overflow-y: auto;
  transition: width 0.3s ease;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  padding: 1rem;
}

.panel-left {
  background-color: #212121;
}

.panel-center {
  flex: 1;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  background-color: #212121;
}

.panel-right {
  background-color: #212121;
}


.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}


.panel-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #e0e0e0;
}

.panel-toggle-icon {
  width: 16px;
  height: 16px;
  cursor: pointer;
  opacity: 0.7;
  color: rgba(255, 255, 255, 0.6);
  transition: opacity 0.2s;
}

.panel-toggle-icon:hover {
  opacity: 1;
}

.panel-actions {
  display: flex;
  gap: 0.25rem;
}

.panel-divider {
  width: 2px;
  background-color: rgba(0, 0, 0, 0.08);
  cursor: col-resize;
  transition: background-color 0.2s;
}

.panel-divider:hover {
  background-color: rgba(0, 0, 0, 0.15);
}

.sources-list {
  margin-top: 1rem;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  margin: 0.25rem 0;
  background-color: #2a2a2a;
  border-radius: 6px;
  font-size: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.source-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.source-name {
  color: #e0e0e0;
  font-weight: 500;
  display: block;
  font-size: 0.875rem;
}

.source-type {
  color: #999;
  font-size: 0.75rem;
  display: block;
  margin-top: 0.125rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #999;
  font-size: 0.875rem;
}

.chat-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 1rem;
}

.empty-chat h3 {
  color: #e0e0e0;
  font-weight: 500;
}

.empty-chat .text-caption {
  color: #999;
}

.upload-icon {
  font-size: 4rem;
  opacity: 0.4;
  color: #666;
}

.upload-zone {
  border: 2px dashed rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #2a2a2a;
  margin-bottom: 1rem;
}

.upload-zone:hover {
  border-color: rgba(255, 255, 255, 0.25);
  background-color: #2f2f2f;
}

.upload-zone.drag-over {
  border-color: #4CAF50;
  background-color: rgba(76, 175, 80, 0.15);
  transform: scale(1.02);
}

.upload-zone.uploading {
  opacity: 0.7;
  cursor: wait;
}

.upload-content {
  user-select: none;
}

.upload-icon-large {
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 0.5rem;
}

.upload-text {
  color: #e0e0e0;
  font-size: 1rem;
  font-weight: 500;
  margin: 0.5rem 0 0.25rem;
}

.upload-subtext {
  color: #999;
  font-size: 0.875rem;
  margin: 0.25rem 0;
}

.upload-hint {
  color: #999;
  font-size: 0.75rem;
  margin-top: 0.5rem;
}

.file-input-hidden {
  display: none;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  line-height: 1.5;
}

.message.user {
  background-color: #e3f2fd;
  color: #1a1a1a;
  align-self: flex-end;
  max-width: 80%;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.message.assistant {
  background-color: #ffffff;
  color: #1a1a1a;
  align-self: flex-start;
  max-width: 80%;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.agent-label {
  font-weight: 600;
  color: #c81517;
  margin-right: 0.5rem;
}

.chat-input-container {
  padding: 1rem;
  padding-bottom: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  gap: 0.5rem;
  align-items: center;
  background-color: #212121;
  position: sticky;
  bottom: 0;
  z-index: 10;
  margin: 0 -1rem -1rem -1rem;
  padding-left: 1rem;
  padding-right: 1rem;
}

.chat-input-container :deep(.v-field) {
  background-color: #2a2a2a !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

.chat-input-container :deep(.v-field__input) {
  color: #e0e0e0 !important;
}

.chat-input-container :deep(.v-field__input::placeholder) {
  color: #999 !important;
  opacity: 1 !important;
}

.chat-input-container :deep(.v-field:hover) {
  border-color: rgba(255, 255, 255, 0.3) !important;
}

.chat-input-container :deep(.v-field--focused) {
  border-color: rgba(255, 255, 255, 0.4) !important;
}

.studio-section {
  margin-bottom: 1.5rem;
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 0.75rem;
}

.tools-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tool-item {
  display: flex;
  align-items: flex-start;
  padding: 0.75rem;
  background-color: #2a2a2a;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  transition: background-color 0.2s;
}

.tool-item :deep(.v-icon) {
  color: #ffffff !important;
}

.tool-item.clickable {
  cursor: pointer;
}

.tool-item.clickable:hover {
  background-color: #2f2f2f;
  border-color: rgba(200, 21, 23, 0.5);
}

.tool-category {
  margin-bottom: 1.5rem;
}

.category-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #999;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
}

.category-title.clickable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.category-title.clickable:hover {
  color: #e0e0e0;
}

.tool-subcategory {
  margin-left: 0.5rem;
  margin-bottom: 1rem;
  padding-left: 0.75rem;
  border-left: 2px solid rgba(255, 255, 255, 0.08);
}

.tool-object-type {
  margin-left: 0.5rem;
  margin-bottom: 0.75rem;
  padding-left: 0.5rem;
}

.object-type-title {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  color: #e0e0e0;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.object-type-title :deep(.v-icon) {
  color: #ffffff !important;
}

.object-type-title.clickable {
  cursor: pointer;
}

.object-type-title.clickable:hover {
  background-color: #2a2a2a;
}

.object-tools-list {
  margin-left: 1rem;
  margin-top: 0.25rem;
  padding-left: 0.75rem;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.subcategory-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  text-transform: none;
}

.subcategory-title :deep(.v-icon) {
  color: #ffffff !important;
}

.subcategory-title.clickable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.subcategory-title.clickable:hover {
  color: #ffffff;
}

.tool-info {
  flex: 1;
}

.tool-name {
  color: #ffffff;
  font-weight: 500;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.tool-desc {
  color: #e0e0e0;
  font-size: 0.75rem;
}

.agent-status {
  padding: 0.75rem;
  background-color: #2a2a2a;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.isms-menu {
  margin-top: 1rem;
}

.isms-menu .menu-category {
  margin-bottom: 0.5rem;
}

.isms-menu .category-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #ffffff;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.isms-menu .category-title.clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.isms-menu .menu-items {
  margin-left: 0.5rem;
  margin-top: 0.25rem;
  padding-left: 0.5rem;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.isms-menu .menu-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  color: #ffffff;
  font-size: 0.875rem;
}

.isms-menu .menu-item span {
  color: #ffffff !important;
}

.isms-menu .menu-item :deep(.v-icon) {
  color: #ffffff !important;
  font-size: 0.875rem;
  border-radius: 4px;
  transition: background-color 0.2s;
  cursor: pointer;
  user-select: none;
}

.isms-menu .menu-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.isms-menu .menu-item :deep(.v-icon) {
  color: #e0e0e0;
}

.isms-menu .menu-item:hover :deep(.v-icon) {
  color: #ffffff;
}

/* Document Processing Menu - same styling as ISMS menu */
.studio-section .menu-items {
  margin-left: 0.5rem;
  margin-top: 0.25rem;
  padding-left: 0.5rem;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.studio-section .menu-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  color: #ffffff;
  font-size: 0.875rem;
}

.studio-section .menu-item span {
  color: #ffffff !important;
}

.studio-section .menu-item :deep(.v-icon) {
  color: #ffffff !important;
  font-size: 0.875rem;
}

.studio-section .menu-item.clickable {
  cursor: pointer;
  user-select: none;
}

.studio-section .menu-item.clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.studio-section .menu-item.clickable:hover :deep(.v-icon) {
  color: #ffffff;
}

.studio-section .category-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #ffffff;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.studio-section .category-title.clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: #c81517;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 0.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  text-align: center;
  padding: 1rem;
}

.error-text {
  color: #ff6b6b;
  font-size: 0.875rem;
  margin: 0.5rem 0;
}

.empty-outputs {
  padding: 1rem;
  background-color: #2a2a2a;
  border-radius: 6px;
  color: #999;
  font-size: 0.875rem;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.panel-collapsed-content {
  padding: 0.5rem;
  display: flex;
  justify-content: center;
}

.notebook-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: #1a1a1a;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.5rem;
  text-align: center;
  font-size: 0.75rem;
  color: #999;
  height: 40px;
  z-index: 5;
}

.message-text {
  white-space: pre-wrap;
  word-wrap: break-word;
}

.table-container {
  margin: 0.5rem 0;
  overflow-x: auto;
  overflow-y: visible;
  max-width: 100%;
  width: 100%;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.3) rgba(0, 0, 0, 0.1);
}

.table-container::-webkit-scrollbar {
  height: 8px;
}

.table-container::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

.table-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
  border-radius: 4px;
}

.table-container::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.5);
}

.data-table {
  width: 100%;
  min-width: max-content;
  border-collapse: collapse;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background-color: #2a2a2a;
  font-size: 0.875rem;
  white-space: nowrap;
}

.data-table thead {
  background-color: #1a1a1a;
}

.data-table th {
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #ffffff;
  border-bottom: 2px solid rgba(255, 255, 255, 0.2);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.data-table th:last-child {
  border-right: none;
}

.data-table td {
  padding: 0.75rem;
  color: #e0e0e0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  white-space: nowrap;
}

.data-table td:last-child {
  border-right: none;
}

.data-table tbody tr:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.table-footer {
  padding: 0.5rem 0.75rem;
  color: #999;
  font-size: 0.8125rem;
  font-style: italic;
}
</style>
