/**
 * Configuration Diff Editor
 * Handles Monaco Editor initialization and UI interactions
 */
class ConfigDiffEditor {
    constructor() {
        this.currentTheme = this.loadSavedTheme();
        this.isSideBySide = true;
        this.diffEditor = null;
        this.editorContainer = null;

        // Prevent multiple initializations
        if (window.configDiffEditorInstance) {
            return window.configDiffEditorInstance;
        }

        window.configDiffEditorInstance = this;
        this.init();
    }

    init() {
        this.editorContainer = document.getElementById('diff-editor');

        // Check if editor container exists and isn't already initialized
        if (!this.editorContainer) {
            console.warn('Diff editor container not found');
            return;
        }

        // Check if Monaco is already attached to this element
        if (this.editorContainer.hasAttribute('data-monaco-initialized')) {
            console.warn('Monaco editor already initialized on this element');
            return;
        }

        this.loadConfigData();
        this.initializeMonacoEditor();
    }

    loadConfigData() {
        const configElement = document.getElementById('config-data');
        if (configElement) {
            try {
                this.configData = JSON.parse(configElement.textContent);
            } catch (e) {
                console.error('Failed to parse configuration data:', e);
                this.configData = { originalConfig: '', modifiedConfig: '' };
            }
        }
    }

    initializeMonacoEditor() {
        require.config({
            paths: {
                'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs'
            }
        });

        require(['vs/editor/editor.main'], () => {
            this.createDiffEditor();
            this.setupEventListeners();
        });
    }

    createDiffEditor() {
        const editorOptions = {
            theme: this.currentTheme,
            readOnly: true,
            renderSideBySide: true,
            originalEditable: false,
            renderWhitespace: 'boundary',
            diffWordWrap: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            lineNumbers: 'on',
            wordWrap: 'on',
            matchBrackets: 'always'
        };

        try {
            // Mark container as initialized before creating editor
            this.editorContainer.setAttribute('data-monaco-initialized', 'true');

            this.diffEditor = monaco.editor.createDiffEditor(
                this.editorContainer,
                editorOptions
            );

            this.setEditorModels();
            this.enableFolding();
            this.toggleHeaders();
            this.initializeThemeButton();
        } catch (error) {
            console.error('Failed to create diff editor:', error);
            // Remove the marker if creation failed
            this.editorContainer.removeAttribute('data-monaco-initialized');
        }
    }

    setEditorModels() {
        const originalModel = monaco.editor.createModel(
            this.configData.originalConfig,
            'xml'
        );
        const modifiedModel = monaco.editor.createModel(
            this.configData.modifiedConfig,
            'xml'
        );

        this.diffEditor.setModel({
            original: originalModel,
            modified: modifiedModel
        });
    }

    enableFolding() {
        this.diffEditor.getOriginalEditor().updateOptions({ folding: true });
        this.diffEditor.getModifiedEditor().updateOptions({ folding: true });
    }

    setupEventListeners() {
        this.setupViewToggle();
        this.setupThemeSelector();
    }

    setupViewToggle() {
        const toggleBtn = document.getElementById('toggle-view-btn');
        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', () => {
            this.toggleView();
        });
    }

    toggleView() {
        this.isSideBySide = !this.isSideBySide;
        this.diffEditor.updateOptions({ renderSideBySide: this.isSideBySide });

        this.updateToggleButton();
        this.toggleHeaders();
    }

    updateToggleButton() {
        const toggleBtn = document.getElementById('toggle-view-btn');
        const toggleIcon = toggleBtn?.querySelector('i');
        const toggleText = toggleBtn?.querySelector('span');

        if (!toggleIcon || !toggleText) return;

        if (this.isSideBySide) {
            toggleIcon.className = 'mdi mdi-view-split-vertical';
            toggleText.textContent = 'Switch to Inline View';
        } else {
            toggleIcon.className = 'mdi mdi-view-sequential';
            toggleText.textContent = 'Switch to Side-by-Side View';
        }
    }

    toggleHeaders() {
        const headerRow = document.querySelector('.row.mb-2');
        if (headerRow) {
            if (this.isSideBySide) {
                headerRow.style.display = 'flex';
            } else {
                headerRow.style.display = 'none';
            }
        }
    }

    setupThemeSelector() {
        document.addEventListener('click', (e) => {
            if (this.isThemeDropdownItem(e.target)) {
                e.preventDefault();
                e.stopPropagation();
                this.changeTheme(e.target);
            }
        });
    }

    isThemeDropdownItem(element) {
        return element.classList.contains('dropdown-item') &&
               element.hasAttribute('data-theme');
    }

    changeTheme(themeElement) {
        const selectedTheme = themeElement.getAttribute('data-theme');
        this.currentTheme = selectedTheme;

        monaco.editor.setTheme(selectedTheme);
        this.updateThemeButton(themeElement.textContent);
        this.saveTheme(selectedTheme);
    }

    updateThemeButton(themeName) {
        const themeBtn = document.getElementById('theme-dropdown');
        const themeText = themeBtn?.querySelector('span');

        if (themeText) {
            themeText.textContent = themeName;
        }
    }

    // Theme persistence methods
    saveTheme(theme) {
        try {
            localStorage.setItem('monaco-editor-theme', theme);
        } catch (e) {
            console.warn('Failed to save theme to localStorage:', e);
        }
    }

    loadSavedTheme() {
        try {
            const savedTheme = localStorage.getItem('monaco-editor-theme');
            return savedTheme || 'vs'; // Default to 'vs' if no saved theme
        } catch (e) {
            console.warn('Failed to load theme from localStorage:', e);
            return 'vs'; // Default to 'vs' if localStorage fails
        }
    }

    initializeThemeButton() {
        // Find the theme label for the current theme
        const themeLabel = this.getThemeLabel(this.currentTheme);
        this.updateThemeButton(themeLabel);
    }

    getThemeLabel(themeValue) {
        const themeMap = {
            'vs': 'Light',
            'vs-dark': 'Dark',
            'hc-black': 'High Contrast Dark',
            'hc-light': 'High Contrast Light'
        };
        return themeMap[themeValue] || 'Light';
    }

    // Cleanup method for proper disposal
    dispose() {
        if (this.diffEditor) {
            this.diffEditor.dispose();
            this.diffEditor = null;
        }

        if (this.editorContainer) {
            this.editorContainer.removeAttribute('data-monaco-initialized');
        }

        // Clear global instance
        if (window.configDiffEditorInstance === this) {
            delete window.configDiffEditorInstance;
        }
    }
}

// Theme configuration
const THEMES = [
    { value: 'vs', label: 'Light' },
    { value: 'vs-dark', label: 'Dark' },
    { value: 'hc-black', label: 'High Contrast Dark' },
    { value: 'hc-light', label: 'High Contrast Light' }
];

// Initialize function that handles multiple scenarios
function initializeConfigDiffEditor() {
    // Only initialize if the diff editor container is present
    if (document.getElementById('diff-editor')) {
        new ConfigDiffEditor();
    }
}

// Handle different loading scenarios for NetBox
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeConfigDiffEditor);
} else {
    // DOM already loaded, initialize immediately
    initializeConfigDiffEditor();
}

// Handle HTMX page updates in NetBox
document.addEventListener('htmx:afterSwap', initializeConfigDiffEditor);
document.addEventListener('htmx:afterSettle', initializeConfigDiffEditor);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.configDiffEditorInstance) {
        window.configDiffEditorInstance.dispose();
    }
});
