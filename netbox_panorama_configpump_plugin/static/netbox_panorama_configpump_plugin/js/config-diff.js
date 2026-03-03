/**
 * Configuration Diff Editor
 * Handles Monaco Editor initialization and UI interactions
 */
class ConfigDiffEditor {
    constructor() {
        this.currentTheme = this.loadSavedTheme();
        this.isSideBySide = true;
        this.currentFormat = 'xml'; // 'xml', 'yaml', or 'json'
        this.diffEditor = null;
        this.editorContainer = null;
        this.originalConfigXml = null;
        this.modifiedConfigXml = null;
        this.originalConfigYaml = null;
        this.modifiedConfigYaml = null;
        this.originalConfigJson = null;
        this.modifiedConfigJson = null;
        this.formatButtons = { yaml: null, json: null };

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
                // Store original XML configs
                this.originalConfigXml = this.configData.originalConfig;
                this.modifiedConfigXml = this.configData.modifiedConfig;
                // Conversions will be done lazily when needed
                this.originalConfigYaml = null;
                this.modifiedConfigYaml = null;
                this.originalConfigJson = null;
                this.modifiedConfigJson = null;
            } catch (e) {
                console.error('Failed to parse configuration data:', e);
                this.configData = { originalConfig: '', modifiedConfig: '' };
                this.originalConfigXml = '';
                this.modifiedConfigXml = '';
                this.originalConfigYaml = '';
                this.modifiedConfigYaml = '';
                this.originalConfigJson = '';
                this.modifiedConfigJson = '';
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
            this.initializeFormatButtons();
            // Also set up format buttons here as a fallback
            this.setupFormatButtons();
        } catch (error) {
            console.error('Failed to create diff editor:', error);
            // Remove the marker if creation failed
            this.editorContainer.removeAttribute('data-monaco-initialized');
        }
    }

    setEditorModels() {
        // Convert to alternate formats if needed and not already converted
        if (this.currentFormat === 'yaml') {
            if (this.originalConfigYaml === null) {
                this.originalConfigYaml = this.xmlToYaml(this.originalConfigXml);
            }
            if (this.modifiedConfigYaml === null) {
                this.modifiedConfigYaml = this.xmlToYaml(this.modifiedConfigXml);
            }
        } else if (this.currentFormat === 'json') {
            if (this.originalConfigJson === null) {
                this.originalConfigJson = this.xmlToJson(this.originalConfigXml);
            }
            if (this.modifiedConfigJson === null) {
                this.modifiedConfigJson = this.xmlToJson(this.modifiedConfigXml);
            }
        }

        let originalContent = this.originalConfigXml;
        let modifiedContent = this.modifiedConfigXml;
        let language = 'xml';

        switch (this.currentFormat) {
            case 'yaml':
                originalContent = this.originalConfigYaml;
                modifiedContent = this.modifiedConfigYaml;
                language = 'yaml';
                break;
            case 'json':
                originalContent = this.originalConfigJson;
                modifiedContent = this.modifiedConfigJson;
                language = 'json';
                break;
            default:
                break;
        }

        const previousModels = this.diffEditor ? this.diffEditor.getModel() : null;

        const originalModel = monaco.editor.createModel(
            originalContent || '',
            language
        );
        const modifiedModel = monaco.editor.createModel(
            modifiedContent || '',
            language
        );

        if (this.diffEditor) {
            this.diffEditor.setModel({
                original: originalModel,
                modified: modifiedModel
            });
        }

        // Dispose previous models after new ones are attached
        if (previousModels) {
            if (previousModels.original) {
                previousModels.original.dispose();
            }
            if (previousModels.modified) {
                previousModels.modified.dispose();
            }
        }
    }

    enableFolding() {
        this.diffEditor.getOriginalEditor().updateOptions({ folding: true });
        this.diffEditor.getModifiedEditor().updateOptions({ folding: true });
    }

    setupEventListeners() {
        this.setupViewToggle();
        this.setupFormatButtons();
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

    setupFormatButtons() {
        const yamlBtn = document.getElementById('toggle-yaml-btn');
        const jsonBtn = document.getElementById('toggle-json-btn');

        this.formatButtons = {
            yaml: yamlBtn || null,
            json: jsonBtn || null
        };

        if (yamlBtn && !yamlBtn.dataset.listenerAttached) {
            yamlBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.handleFormatButtonClick('yaml');
            });
            yamlBtn.dataset.listenerAttached = 'true';
        }

        if (jsonBtn && !jsonBtn.dataset.listenerAttached) {
            jsonBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.handleFormatButtonClick('json');
            });
            jsonBtn.dataset.listenerAttached = 'true';
        }

        this.updateFormatButtons();
    }

    handleFormatButtonClick(targetFormat) {
        const newFormat = this.currentFormat === targetFormat ? 'xml' : targetFormat;
        this.setFormat(newFormat);
    }

    setFormat(format) {
        if (!['xml', 'yaml', 'json'].includes(format)) {
            console.warn('Unsupported format requested:', format);
            return;
        }

        if (this.currentFormat === format) {
            this.updateFormatButtons();
            return;
        }

        const previousFormat = this.currentFormat;

        try {
            this.currentFormat = format;
            this.setEditorModels();
            this.updateFormatButtons();
        } catch (error) {
            console.error('Error setting format:', error);
            this.currentFormat = previousFormat;
            this.setEditorModels();
            this.updateFormatButtons();
        }
    }

    updateFormatButtons() {
        const yamlBtn = this.formatButtons?.yaml || document.getElementById('toggle-yaml-btn');
        const jsonBtn = this.formatButtons?.json || document.getElementById('toggle-json-btn');

        if (yamlBtn) {
            this.formatButtons.yaml = yamlBtn;
            const yamlIcon = yamlBtn.querySelector('i');
            const yamlText = yamlBtn.querySelector('span');

            if (yamlIcon) {
                yamlIcon.className = this.currentFormat === 'yaml'
                    ? 'mdi mdi-xml'
                    : 'mdi mdi-code-braces';
            }
            if (yamlText) {
                yamlText.textContent = this.currentFormat === 'yaml'
                    ? 'Switch to XML'
                    : 'Switch to YAML';
            }
        }

        if (jsonBtn) {
            this.formatButtons.json = jsonBtn;
            const jsonIcon = jsonBtn.querySelector('i');
            const jsonText = jsonBtn.querySelector('span');

            if (jsonIcon) {
                jsonIcon.className = this.currentFormat === 'json'
                    ? 'mdi mdi-xml'
                    : 'mdi mdi-code-json';
            }
            if (jsonText) {
                jsonText.textContent = this.currentFormat === 'json'
                    ? 'Switch to XML'
                    : 'Switch to JSON';
            }
        }
    }

    initializeFormatButtons() {
        this.updateFormatButtons();
    }

    xmlToYaml(xmlString) {
        const { success, data, errorMessage } = this.convertXmlToObject(xmlString);

        if (!success) {
            return errorMessage;
        }

        if (!data) {
            return '';
        }

        const yamlLib = window.jsyaml || (typeof jsyaml !== 'undefined' ? jsyaml : null);

        if (yamlLib && yamlLib.dump) {
            try {
                return yamlLib.dump(data, {
                    indent: 2,
                    lineWidth: -1,
                    noRefs: true,
                    sortKeys: false
                });
            } catch (error) {
                console.error('Error converting object to YAML:', error);
                return '# Error converting XML to YAML:\n# ' + error.message + '\n' + xmlString;
            }
        }

        console.error('js-yaml library not available for YAML conversion');
        return '# Error: YAML library not available\n# Please ensure js-yaml static asset is loaded\n' + xmlString;
    }

    xmlToJson(xmlString) {
        const { success, data, errorMessage } = this.convertXmlToObject(xmlString);

        if (!success) {
            return errorMessage;
        }

        if (!data) {
            return '';
        }

        try {
            return JSON.stringify(data, null, 2);
        } catch (error) {
            console.error('Error converting XML to JSON:', error);
            return '# Error converting XML to JSON:\n# ' + error.message + '\n' + xmlString;
        }
    }

    convertXmlToObject(xmlString) {
        if (!xmlString || !xmlString.trim()) {
            return { success: true, data: null };
        }

        try {
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(xmlString, 'text/xml');

            const parseError = xmlDoc.querySelector('parsererror');
            if (parseError) {
                console.warn('XML parsing error:', parseError.textContent);
                return { success: false, errorMessage: '# Error: Invalid XML\n' + xmlString };
            }

            const rootElement = xmlDoc.documentElement;
            if (!rootElement) {
                return { success: false, errorMessage: '# Error: No root element found\n' + xmlString };
            }

            const data = {};
            data[rootElement.nodeName] = this.xmlNodeToObject(rootElement);
            return { success: true, data };
        } catch (error) {
            console.error('Error parsing XML:', error);
            return { success: false, errorMessage: '# Error converting XML:\n# ' + error.message + '\n' + xmlString };
        }
    }

    xmlNodeToObject(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent.trim();
            return text || null;
        }

        if (node.nodeType !== Node.ELEMENT_NODE) {
            return null;
        }

        const result = {};
        const children = Array.from(node.childNodes).filter((child) => {
            if (child.nodeType === Node.ELEMENT_NODE) {
                return true;
            }
            if (child.nodeType === Node.TEXT_NODE) {
                return child.textContent.trim().length > 0;
            }
            return false;
        });

        if (node.attributes && node.attributes.length > 0) {
            result['@attributes'] = {};
            Array.from(node.attributes).forEach((attr) => {
                result['@attributes'][attr.name] = attr.value;
            });
        }

        if (children.length === 0) {
            const textContent = node.textContent.trim();
            if (textContent) {
                if (result['@attributes']) {
                    result['#text'] = textContent;
                    return result;
                }
                return textContent;
            }
            return result['@attributes'] ? result : null;
        }

        if (children.length === 1 && children[0].nodeType === Node.TEXT_NODE) {
            const text = children[0].textContent.trim();
            if (result['@attributes']) {
                if (text) {
                    result['#text'] = text;
                }
                return result;
            }
            return text;
        }

        const childObj = {};
        children.forEach((child) => {
            if (child.nodeType === Node.TEXT_NODE) {
                const text = child.textContent.trim();
                if (text) {
                    childObj['#text'] = text;
                }
                return;
            }

            const childName = child.nodeName;
            const childValue = this.xmlNodeToObject(child);

            if (childObj[childName]) {
                if (!Array.isArray(childObj[childName])) {
                    childObj[childName] = [childObj[childName]];
                }
                childObj[childName].push(childValue);
            } else {
                childObj[childName] = childValue;
            }
        });

        if (result['@attributes']) {
            return Object.assign({}, result['@attributes'], childObj);
        }

        return childObj;
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

// Handle browser back/forward cache (bfcache) restores
// When returning to the page via back/forward, scripts are not re-run.
// Use pageshow to reinitialize or relayout the editor so the diff is visible.
function relayoutOrReinitializeDiffEditor() {
    const instance = window.configDiffEditorInstance;
    const container = document.getElementById('diff-editor');

    if (!container) {
        return;
    }

    if (instance && instance.diffEditor) {
        try {
            instance.diffEditor.layout();
        } catch (e) {
            // If layout fails (e.g., disposed), try to re-init
            container.removeAttribute('data-monaco-initialized');
            initializeConfigDiffEditor();
        }
    } else {
        // If we have a stale initialized marker but no instance, clear and re-init
        container.removeAttribute('data-monaco-initialized');
        initializeConfigDiffEditor();
    }
}

window.addEventListener('pageshow', (event) => {
    // Always attempt to relayout/reinit on pageshow, including bfcache restores
    relayoutOrReinitializeDiffEditor();
});

// Dispose on pagehide to avoid stale state across BFCache navigations
window.addEventListener('pagehide', () => {
    if (window.configDiffEditorInstance) {
        window.configDiffEditorInstance.dispose();
    }
});
