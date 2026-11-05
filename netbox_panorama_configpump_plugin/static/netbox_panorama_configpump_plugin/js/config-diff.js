/**
 * Configuration Diff Editor
 * Handles Monaco Editor initialization and UI interactions
 */

const DIFF_EDITOR_CURSOR_OPTIONS = {
    cursorStyle: 'line',
    cursorWidth: 3,
    cursorBlinking: 'blink',
    renderLineHighlight: 'all'
};

class ConfigDiffEditor {
    constructor() {
        // Prevent multiple initializations
        if (window.configDiffEditorInstance) {
            return window.configDiffEditorInstance;
        }

        this.currentTheme = this.loadSavedTheme();
        this.isSideBySide = true;
        this.currentFormat = this.loadSavedFormat(); // 'xml', 'yaml', or 'json'
        this.hideUnchangedEnabled = this.loadSavedHideUnchanged(); // default: show all lines
        this.contextLineCount = this.loadSavedContextLineCount();
        this.diffEditor = null;
        this.editorContainer = null;
        this.yamlPathByLine = [];
        this.yamlPathByLineOriginal = [];
        this.yamlPathStatusElement = null;
        this.lastYamlPath = null;
        this.lineChanges = [];
        this.currentChangeIndex = -1;
        this.changeNavigationInitialized = false;
        this.changeIndexListenerAttached = false;
        this.changeNavHighlightEditor = null;
        this.changeNavDecorationIds = [];
        this.inlineDeletedHighlightEls = [];
        this.navSuppressedLineHighlight = false;
        this.formatError = null;
        this.originalConfigXml = null;
        this.modifiedConfigXml = null;
        this.originalConfigYaml = null;
        this.modifiedConfigYaml = null;
        this.originalConfigJson = null;
        this.modifiedConfigJson = null;
        this.formatButtons = { yaml: null, json: null };

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
        const amdRequire = (typeof window !== 'undefined' && window.require)
            ? window.require
            : (typeof require !== 'undefined' ? require : null);

        if (!amdRequire || typeof amdRequire !== 'function' || typeof amdRequire.config !== 'function') {
            console.error('Monaco AMD loader (require) is not available');
            return;
        }

        const vsPath = window.MONACO_VS_BASE;
        if (!vsPath) {
            console.error('MONACO_VS_BASE is not set; cannot load Monaco Editor');
            return;
        }

        amdRequire.config({
            paths: {
                'vs': vsPath
            }
        });

        amdRequire(['vs/editor/editor.main'], () => {
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
            matchBrackets: 'always',
            stickyScroll: {
                enabled: true
            },
            hideUnchangedRegions: this.getHideUnchangedOptions(),
            renderIndicators: true,
            renderOverviewRuler: true,
            renderIndentGuides: true,
            ...DIFF_EDITOR_CURSOR_OPTIONS,
            scrollbar: {
                useShadows: false,
                verticalHasArrows: true,
                horizontalHasArrows: true,
            }
        };

        try {
            // Mark container as initialized before creating editor
            this.editorContainer.setAttribute('data-monaco-initialized', 'true');

            this.diffEditor = monaco.editor.createDiffEditor(
                this.editorContainer,
                editorOptions
            );

            this.setEditorModels();
            this.attachChangeIndexListener();
            this.applySharedEditorOptions();
            this.initializeYamlPathStatus();
            this.buildChangeIndex();
            this.setupChangeNavigation();
            this.toggleHeaders();
            this.initializeThemeButton();
            this.setupHideUnchangedToggle();
        } catch (error) {
            console.error('Failed to create diff editor:', error);
            // Remove the marker if creation failed
            this.editorContainer.removeAttribute('data-monaco-initialized');
        }
    }

    setEditorModels() {
        // Convert to alternate formats if needed and not already converted
        this.formatError = null;

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

        this.clearYamlPathStatus();
        this.buildYamlPathIndex(modifiedContent, language);
        this.buildChangeIndex();
        this.updateFormatErrorBanner();

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

    applySharedEditorOptions() {
        const sharedOptions = {
            folding: true,
            ...DIFF_EDITOR_CURSOR_OPTIONS
        };
        this.diffEditor.getOriginalEditor().updateOptions(sharedOptions);
        this.diffEditor.getModifiedEditor().updateOptions(sharedOptions);
    }

    getHideUnchangedOptions() {
        return {
            enabled: this.hideUnchangedEnabled,
            contextLineCount: this.contextLineCount,
            minimumLineCount: 3,
            revealLineCount: 5,
            hideControls: 'mouseOver'
        };
    }

    setupEventListeners() {
        this.setupViewToggle();
        this.setupFormatButtons();
        this.setupThemeSelector();
        this.setupContextLineInput();
        this.setupYamlPathCursorListener();
    }

    setupHideUnchangedToggle() {
        const btn = document.getElementById('toggle-hide-unchanged-btn');
        if (!btn || btn.dataset.listenerAttached) {
            return;
        }

        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleHideUnchangedRegions();
        });
        btn.dataset.listenerAttached = 'true';

        this.updateHideUnchangedButton();
    }

    toggleHideUnchangedRegions() {
        this.hideUnchangedEnabled = !this.hideUnchangedEnabled;

        this.saveHideUnchanged(this.hideUnchangedEnabled);

        if (this.diffEditor && this.diffEditor.updateOptions) {
            this.diffEditor.updateOptions({
                hideUnchangedRegions: this.getHideUnchangedOptions(),
                stickyScroll: {
                    enabled: true
                }
            });
        }

        this.updateHideUnchangedButton();
    }

    setupContextLineInput() {
        const input = document.getElementById('context-line-count-input');
        if (!input || input.dataset.listenerAttached) {
            return;
        }

        input.value = this.contextLineCount;

        input.addEventListener('change', (e) => {
            const value = parseInt(e.target.value, 10);
            if (Number.isNaN(value) || value < 0) {
                // Revert to the last valid value
                e.target.value = this.contextLineCount;
                return;
            }

            const previousContext = this.contextLineCount;
            this.contextLineCount = value;
            this.saveContextLineCount(value);

            if (this.diffEditor && this.diffEditor.updateOptions) {
                this.diffEditor.updateOptions({
                    hideUnchangedRegions: this.getHideUnchangedOptions()
                });

                // If we reduced the context, force Monaco to fully
                // recompute the diff & hidden regions by rebuilding
                // the models. This resets any manual “show more”
                // expansions so the number of visible context lines
                // matches the new value immediately.
                if (this.hideUnchangedEnabled && value < previousContext) {
                    this.setEditorModels();
                }
            }
        });

        input.dataset.listenerAttached = 'true';
    }

    updateHideUnchangedButton() {
        const btn = document.getElementById('toggle-hide-unchanged-btn');
        if (!btn) return;

        const icon = btn.querySelector('i');
        const text = btn.querySelector('span');

        if (icon) {
            icon.className = this.hideUnchangedEnabled
                ? 'mdi mdi-page-layout-header'
                : 'mdi mdi-page-layout-body';
        }

        if (text) {
            text.textContent = this.hideUnchangedEnabled
                ? 'Show all lines'
                : 'Hide unchanged';
        }
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
            this.saveFormat(format);
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

            yamlBtn.classList.remove('btn-outline-secondary', 'btn-primary');
            if (this.currentFormat === 'yaml') {
                yamlBtn.classList.add('btn-primary');
            } else {
                yamlBtn.classList.add('btn-outline-secondary');
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

            jsonBtn.classList.remove('btn-outline-secondary', 'btn-primary');
            if (this.currentFormat === 'json') {
                jsonBtn.classList.add('btn-primary');
            } else {
                jsonBtn.classList.add('btn-outline-secondary');
            }
        }
    }

    xmlToYaml(xmlString) {
        const { success, data, errorMessage } = this.convertXmlToObject(xmlString);

        if (!success) {
            this.formatError = 'Error converting XML to YAML';
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
                this.formatError = 'Error converting XML to YAML: ' + error.message;
                return '# Error converting XML to YAML:\n# ' + error.message + '\n' + xmlString;
            }
        }

        console.error('js-yaml library not available for YAML conversion');
        this.formatError = 'YAML library is not available; YAML view shows a fallback.';
        return '# Error: YAML library not available\n# Please ensure js-yaml static asset is loaded\n' + xmlString;
    }

    xmlToJson(xmlString) {
        const { success, data, errorMessage } = this.convertXmlToObject(xmlString);

        if (!success) {
            this.formatError = 'Error converting XML to JSON';
            return errorMessage;
        }

        if (!data) {
            return '';
        }

        try {
            return JSON.stringify(data, null, 2);
        } catch (error) {
            console.error('Error converting XML to JSON:', error);
            this.formatError = 'Error converting XML to JSON: ' + error.message;
            return '// Error converting XML to JSON:\n// ' + error.message + '\n' + xmlString;
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
            result._attributes = {};
            Array.from(node.attributes).forEach((attr) => {
                result._attributes[attr.name] = attr.value;
            });
        }

        if (children.length === 0) {
            const textContent = node.textContent.trim();
            if (textContent) {
                if (result._attributes) {
                    result['#text'] = textContent;
                    return result;
                }
                return textContent;
            }
            return result._attributes ? result : null;
        }

        if (children.length === 1 && children[0].nodeType === Node.TEXT_NODE) {
            const text = children[0].textContent.trim();
            if (result._attributes) {
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

        if (result._attributes) {
            return Object.assign({}, result._attributes, childObj);
        }

        return childObj;
    }

    // Build a simple YAML path index per line for the modified model
    buildYamlPathIndex(content, language) {
        const helper = (window.ConfigDiffYamlPath || {}).buildYamlPathIndex;
        if (!helper) {
            this.yamlPathByLine = [];
            this.yamlPathByLineOriginal = [];
            this.updateYamlPathStatus(null);
            return;
        }

        const originalContent = language === 'xml'
            ? this.originalConfigXml
            : this.originalConfigYaml;
        const { modifiedPaths, originalPaths } = helper(content, originalContent, language);
        this.yamlPathByLine = modifiedPaths;
        this.yamlPathByLineOriginal = originalPaths;

        if (!modifiedPaths.length) {
            this.updateYamlPathStatus(null);
        }
    }

    initializeYamlPathStatus() {
        if (this.yamlPathStatusElement) return;
        this.yamlPathStatusElement = document.getElementById('yaml-path-status');
        if (!this.yamlPathStatusElement) {
            return;
        }
        this.updateYamlPathStatus(null);
        if (!this.yamlPathStatusElement.dataset.clickListenerAttached) {
            this.yamlPathStatusElement.addEventListener('click', (e) => {
                const segment = e.target.closest('.yaml-path-segment');
                if (!segment || !this.yamlPathStatusElement.contains(segment)) {
                    return;
                }
                const rawIndex = segment.getAttribute('data-path-index');
                if (rawIndex == null) {
                    return;
                }
                const pathIndex = parseInt(rawIndex, 10);
                if (Number.isNaN(pathIndex)) {
                    return;
                }
                e.preventDefault();
                this.jumpToYamlPathPrefix(pathIndex);
            });
            this.yamlPathStatusElement.dataset.clickListenerAttached = 'true';
        }
    }

    pathSegments(path) {
        if (Array.isArray(path)) {
            return path.filter(Boolean);
        }
        if (path == null || path === '') {
            return [];
        }
        return String(path).split('.').filter(Boolean);
    }

    clearYamlPathStatus() {
        this.lastYamlPath = null;
        if (this.yamlPathStatusElement) {
            this.yamlPathStatusElement.textContent = '';
        }
    }

    jumpToYamlPathPrefix(pathIndex) {
        const segments = this.pathSegments(this.lastYamlPath);
        if (!segments.length || pathIndex < 0 || pathIndex >= segments.length) {
            return;
        }

        const prefix = segments.slice(0, pathIndex + 1);
        const indexArray = this.yamlPathByLine || [];
        let targetLine = -1;

        for (let i = 0; i < indexArray.length; i += 1) {
            const lineSegments = this.pathSegments(indexArray[i]);
            if (lineSegments.length < prefix.length) {
                continue;
            }
            let matches = true;
            for (let j = 0; j < prefix.length; j += 1) {
                if (lineSegments[j] !== prefix[j]) {
                    matches = false;
                    break;
                }
            }
            if (matches) {
                targetLine = i + 1; // Monaco line numbers are 1-based
                break;
            }
        }

        if (targetLine < 1 || !this.diffEditor) {
            return;
        }

        const modified = this.diffEditor.getModifiedEditor();
        this.focusDiffEditorAtLine(modified, targetLine, 'modified');
    }

    setupYamlPathCursorListener() {
        if (!this.diffEditor) return;
        const modified = this.diffEditor.getModifiedEditor();
        const original = this.diffEditor.getOriginalEditor();

        if (!modified && !original) {
            return;
        }

        const debouncedUpdate = this.debounce((position, side) => {
            this.updateYamlPathFromPosition(position, side);
        }, 80);

        if (modified && !modified._yamlPathListenerAttached) {
            modified.onDidChangeCursorPosition((e) => {
                debouncedUpdate(e.position, 'modified');
            });
            modified._yamlPathListenerAttached = true;
        }

        if (original && !original._yamlPathListenerAttached) {
            original.onDidChangeCursorPosition((e) => {
                debouncedUpdate(e.position, 'original');
            });
            original._yamlPathListenerAttached = true;
        }
    }

    updateYamlPathFromPosition(position, side = 'modified') {
        if (!position) {
            this.updateYamlPathStatus(null);
            return;
        }
        this.updateYamlPathFromLineNumber(position.lineNumber, side);
    }

    updateYamlPathFromLineNumber(lineNumber, side = 'modified') {
        if (this.currentFormat !== 'yaml' && this.currentFormat !== 'xml') {
            this.updateYamlPathStatus(null);
            return;
        }

        const indexArray = side === 'original'
            ? (this.yamlPathByLineOriginal || [])
            : (this.yamlPathByLine || []);

        if (!indexArray.length || typeof lineNumber !== 'number') {
            this.updateYamlPathStatus(null);
            return;
        }

        const index = Math.max(0, Math.min(indexArray.length - 1, lineNumber - 1));
        const path = indexArray[index];
        if (!path || (Array.isArray(path) && !path.length)) {
            this.updateYamlPathStatus(null);
            return;
        }
        this.updateYamlPathStatus(path);
    }

    updateYamlPathStatus(path) {
        if (!this.yamlPathStatusElement) return;
        if (!path || (Array.isArray(path) && !path.length)) {
            // If we have never shown a path yet, keep it empty.
            // Otherwise, retain the last known path so it stays visible
            // until the user selects a new meaningful location.
            if (!this.lastYamlPath) {
                this.yamlPathStatusElement.textContent = '';
            }
            return;
        }

        this.lastYamlPath = path;
        const html = this.renderYamlPath(path);
        // Just show the path itself, without a fixed label prefix
        this.yamlPathStatusElement.innerHTML = html;
    }

    renderYamlPath(path) {
        const segments = this.pathSegments(path);
        if (!segments.length) {
            return Array.isArray(path) ? '' : this.escapeHtml(path);
        }

        return segments
            .map((segment, index) => {
                const isFirst = index === 0;
                const isLast = index === segments.length - 1;
                const classes = ['yaml-path-segment'];

                if (isFirst) {
                    classes.push('yaml-path-segment-root');
                }
                if (isLast) {
                    classes.push('yaml-path-segment-leaf');
                }
                if (!isFirst && !isLast) {
                    classes.push('yaml-path-segment-inner');
                }

                const safeText = (window.ConfigDiffUtils || {}).escapeHtml
                    ? window.ConfigDiffUtils.escapeHtml(segment)
                    : this.escapeHtml(segment);
                return `<span class="${classes.join(' ')}" data-path-index="${index}">${safeText}</span>`;
            })
            .join('<span class="yaml-path-separator">&nbsp;/&nbsp;</span>');
    }

    escapeHtml(text) {
        if ((window.ConfigDiffUtils || {}).escapeHtml) {
            return window.ConfigDiffUtils.escapeHtml(text);
        }
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Simple debounce helper
    debounce(fn, delay) {
        if ((window.ConfigDiffUtils || {}).debounce) {
            return window.ConfigDiffUtils.debounce(fn, delay, this);
        }
        let timer = null;
        return (...args) => {
            if (timer) {
                clearTimeout(timer);
            }
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // Change navigation helpers
    buildChangeIndex() {
        if (!this.diffEditor || typeof this.diffEditor.getLineChanges !== 'function') {
            this.lineChanges = [];
            this.currentChangeIndex = -1;
            return;
        }

        const changes = this.diffEditor.getLineChanges() || [];
        // Sort by modified start line for navigation
        changes.sort((a, b) => {
            return (a.modifiedStartLineNumber || 0) - (b.modifiedStartLineNumber || 0);
        });
        this.lineChanges = changes;
        this.currentChangeIndex = changes.length ? 0 : -1;
    }

    attachChangeIndexListener() {
        if (!this.diffEditor || this.changeIndexListenerAttached) {
            return;
        }

        if (typeof this.diffEditor.onDidUpdateDiff === 'function') {
            this.diffEditor.onDidUpdateDiff(() => {
                this.buildChangeIndex();
            });
            this.changeIndexListenerAttached = true;
        }
    }

    setupChangeNavigation() {
        if (this.changeNavigationInitialized) return;
        this.changeNavigationInitialized = true;

        const prevBtn = document.getElementById('prev-change-btn');
        const nextBtn = document.getElementById('next-change-btn');

        if (prevBtn && !prevBtn.dataset.listenerAttached) {
            prevBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.goToChange(-1);
            });
            prevBtn.dataset.listenerAttached = 'true';
        }

        if (nextBtn && !nextBtn.dataset.listenerAttached) {
            nextBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.goToChange(1);
            });
            nextBtn.dataset.listenerAttached = 'true';
        }

        // Keyboard shortcuts on both panes (focus moves between them on nav)
        if (this.diffEditor) {
            const bindChangeNav = (editor) => {
                if (!editor || editor._changeNavigationKeybindingsAttached) {
                    return;
                }
                editor.addCommand(monaco.KeyMod.Alt | monaco.KeyCode.UpArrow, () => {
                    this.goToChange(-1);
                });
                editor.addCommand(monaco.KeyMod.Alt | monaco.KeyCode.DownArrow, () => {
                    this.goToChange(1);
                });
                editor._changeNavigationKeybindingsAttached = true;
            };
            bindChangeNav(this.diffEditor.getModifiedEditor());
            bindChangeNav(this.diffEditor.getOriginalEditor());
        }
    }

    /**
     * Monaco ILineChange: deletion has modifiedEndLineNumber === 0,
     * insertion has originalEndLineNumber === 0; otherwise both sides changed.
     */
    getChangeFocusSide(change) {
        const originalHasLines = (change.originalEndLineNumber || 0) > 0;
        const modifiedHasLines = (change.modifiedEndLineNumber || 0) > 0;

        if (originalHasLines && !modifiedHasLines) {
            return 'original'; // deletion — left pane
        }
        if (modifiedHasLines && !originalHasLines) {
            return 'modified'; // insertion — right pane
        }
        // Modification (or unclear): prefer NetBox / modified side
        return 'modified';
    }

    clearChangeNavHighlight() {
        if (this.changeNavHighlightEditor && typeof this.changeNavHighlightEditor.deltaDecorations === 'function') {
            this.changeNavHighlightEditor.deltaDecorations(this.changeNavDecorationIds || [], []);
        }
        this.changeNavHighlightEditor = null;
        this.changeNavDecorationIds = [];
        this.clearInlineDeletedDomHighlight();
        this.restoreNavLineHighlight();
    }

    restoreNavLineHighlight() {
        if (!this.navSuppressedLineHighlight || !this.diffEditor) {
            return;
        }
        const modified = this.diffEditor.getModifiedEditor();
        if (modified && typeof modified.updateOptions === 'function') {
            modified.updateOptions({ renderLineHighlight: 'all' });
        }
        this.navSuppressedLineHighlight = false;
    }

    clearInlineDeletedDomHighlight() {
        (this.inlineDeletedHighlightEls || []).forEach((el) => {
            if (el && el.classList) {
                el.classList.remove('config-diff-nav-inline-deleted');
            }
        });
        this.inlineDeletedHighlightEls = [];
        if (this.editorContainer) {
            this.editorContainer.querySelectorAll('.config-diff-nav-inline-deleted').forEach((el) => {
                el.classList.remove('config-diff-nav-inline-deleted');
            });
        }
    }

    getEditorLineHeight(editor) {
        if (
            typeof monaco !== 'undefined'
            && monaco.editor
            && monaco.editor.EditorOption
            && editor
            && typeof editor.getOption === 'function'
        ) {
            return editor.getOption(monaco.editor.EditorOption.lineHeight) || 18;
        }
        return 18;
    }

    getViewZonePositionedParent(node, zonesParent) {
        let positioned = node;
        while (
            positioned
            && positioned !== zonesParent
            && !(positioned.style && positioned.style.top)
        ) {
            positioned = positioned.parentElement;
        }
        if (!positioned || positioned === zonesParent) {
            return node.parentElement || node;
        }
        return positioned;
    }

    resolveViewZoneTop(positioned) {
        const top = parseFloat((positioned.style && positioned.style.top) || '');
        return Number.isFinite(top) ? top : (positioned.offsetTop || 0);
    }

    /**
     * Inline diff renders deletions as view-zones on the modified editor
     * (.view-lines.line-delete). Original-editor decorations are not shown.
     */
    highlightInlineDeletedChange(change) {
        const modified = this.diffEditor ? this.diffEditor.getModifiedEditor() : null;
        if (!modified) {
            return;
        }

        this.clearChangeNavHighlight();

        const anchorLine = Math.max(1, change.modifiedStartLineNumber || 1);
        const originalLine = Math.max(1, change.originalStartLineNumber || 1);
        const model = typeof modified.getModel === 'function' ? modified.getModel() : null;
        const lastLine = model ? model.getLineCount() : anchorLine;
        const lineHeight = this.getEditorLineHeight(modified);

        if (typeof modified.focus === 'function') {
            modified.focus();
        }
        if (typeof modified.revealLineInCenter === 'function') {
            modified.revealLineInCenter(Math.min(lastLine, Math.max(1, anchorLine)));
        }

        // Do not paint the unchanged anchor line as the current selection.
        if (typeof modified.updateOptions === 'function') {
            modified.updateOptions({ renderLineHighlight: 'none' });
            this.navSuppressedLineHighlight = true;
        }
        if (typeof modified.setSelection === 'function') {
            modified.setSelection({
                startLineNumber: anchorLine,
                startColumn: 1,
                endLineNumber: anchorLine,
                endColumn: 1
            });
        }

        const markDeletedNodes = () => {
            // Must scope to the modified editor — original also has .view-zones in inline mode
            const modifiedDom = typeof modified.getDomNode === 'function'
                ? modified.getDomNode()
                : null;
            const zonesParent = modifiedDom
                ? modifiedDom.querySelector('.view-zones')
                : null;
            if (!zonesParent || !modifiedDom) {
                return false;
            }

            const deletedNodes = zonesParent.querySelectorAll('.view-lines.line-delete');
            if (!deletedNodes.length) {
                return false;
            }

            // Prefer viewport geometry: zone sits just below the unchanged anchor line
            let anchorBottomY = null;
            if (typeof modified.getScrolledVisiblePosition === 'function') {
                const anchorPos = modified.getScrolledVisiblePosition({
                    lineNumber: anchorLine,
                    column: 1
                });
                if (anchorPos && typeof anchorPos.top === 'number') {
                    const editorRect = modifiedDom.getBoundingClientRect();
                    anchorBottomY = editorRect.top + anchorPos.top + (anchorPos.height || lineHeight);
                }
            }

            let bestNode = null;
            let bestPos = null;
            let bestDist = Infinity;

            deletedNodes.forEach((node) => {
                const rect = node.getBoundingClientRect();
                if (!rect.height && !rect.width) {
                    return; // not laid out / not visible
                }
                const positioned = this.getViewZonePositionedParent(node, zonesParent);
                let dist;
                if (anchorBottomY != null) {
                    // Deleted block should start immediately under the anchor line
                    dist = Math.abs(rect.top - anchorBottomY);
                } else {
                    const resolvedTop = this.resolveViewZoneTop(positioned);
                    const expectedTop = typeof modified.getTopForLineNumber === 'function'
                        ? modified.getTopForLineNumber(anchorLine) + lineHeight
                        : 0;
                    dist = Math.abs(resolvedTop - expectedTop);
                }
                if (dist < bestDist) {
                    bestDist = dist;
                    bestNode = node;
                    bestPos = positioned;
                }
            });

            // Reject matches that are clearly unrelated (far from the anchor)
            const maxDist = Math.max(lineHeight * 6, 48);
            if (!bestNode || bestDist > maxDist) {
                return false;
            }

            const unique = Array.from(new Set([bestNode, bestPos].filter(Boolean)));
            unique.forEach((el) => el.classList.add('config-diff-nav-inline-deleted'));
            this.inlineDeletedHighlightEls = unique;
            return true;
        };

        const retryMark = (attempt) => {
            if (markDeletedNodes() || attempt >= 5) {
                return;
            }
            setTimeout(() => retryMark(attempt + 1), 30 * (attempt + 1));
        };
        requestAnimationFrame(() => retryMark(0));

        this.updateYamlPathFromLineNumber(originalLine, 'original');
    }

    focusDiffEditorAtLine(editor, lineNumber, side, options = {}) {
        if (!editor) {
            return;
        }
        const {
            highlightKind = null,
            pathLine = null,
            pathSide = null,
            endLineNumber = null
        } = options;
        const line = Math.max(1, lineNumber || 1);
        const endLine = Math.max(line, endLineNumber || line);
        const model = typeof editor.getModel === 'function' ? editor.getModel() : null;
        const endColumn = model && typeof model.getLineMaxColumn === 'function'
            ? model.getLineMaxColumn(endLine)
            : 1;

        this.clearChangeNavHighlight();

        if (typeof editor.focus === 'function') {
            editor.focus();
        }
        if (typeof editor.revealLineInCenter === 'function') {
            editor.revealLineInCenter(line);
        }
        if (typeof editor.setSelection === 'function') {
            editor.setSelection({
                startLineNumber: line,
                startColumn: 1,
                endLineNumber: endLine,
                endColumn
            });
        } else if (typeof editor.setPosition === 'function') {
            editor.setPosition({ lineNumber: line, column: 1 });
        }

        if (typeof editor.deltaDecorations === 'function' && typeof monaco !== 'undefined' && monaco.Range) {
            const isDeleted = highlightKind === 'deleted';
            const className = isDeleted
                ? 'config-diff-nav-line config-diff-nav-line-deleted'
                : 'config-diff-nav-line';
            this.changeNavDecorationIds = editor.deltaDecorations([], [{
                range: new monaco.Range(line, 1, endLine, endColumn),
                options: {
                    isWholeLine: true,
                    className,
                    linesDecorationsClassName: isDeleted
                        ? 'config-diff-nav-glyph-deleted'
                        : 'config-diff-nav-glyph',
                    overviewRuler: {
                        color: isDeleted ? 'rgba(253, 126, 20, 0.95)' : 'rgba(13, 110, 253, 0.85)',
                        position: monaco.editor.OverviewRulerLane
                            ? monaco.editor.OverviewRulerLane.Full
                            : 2
                    }
                }
            }]);
            this.changeNavHighlightEditor = editor;
        }

        this.updateYamlPathFromLineNumber(
            pathLine != null ? pathLine : line,
            pathSide || side
        );
    }

    goToChange(direction) {
        if (!this.diffEditor || !this.lineChanges.length) {
            return;
        }

        if (direction === 0) {
            // Stay on current
        } else if (direction > 0) {
            this.currentChangeIndex = (this.currentChangeIndex + 1 + this.lineChanges.length) % this.lineChanges.length;
        } else if (direction < 0) {
            this.currentChangeIndex = (this.currentChangeIndex - 1 + this.lineChanges.length) % this.lineChanges.length;
        }

        const change = this.lineChanges[this.currentChangeIndex];
        if (!change) return;

        const originalEditor = this.diffEditor.getOriginalEditor();
        const modifiedEditor = this.diffEditor.getModifiedEditor();

        const targetOriginalLine = change.originalStartLineNumber || 1;
        const targetOriginalEnd = change.originalEndLineNumber || targetOriginalLine;
        const targetModifiedLine = change.modifiedStartLineNumber || 1;
        const targetModifiedEnd = change.modifiedEndLineNumber || targetModifiedLine;
        const isDeletion = this.getChangeFocusSide(change) === 'original';

        // Keep both models scrolled so inline deleted view-zones stay in view
        if (originalEditor && typeof originalEditor.revealLineInCenter === 'function') {
            originalEditor.revealLineInCenter(targetOriginalLine);
        }
        if (modifiedEditor && typeof modifiedEditor.revealLineInCenter === 'function') {
            // For deletions Monaco's modifiedStartLineNumber is "line after which
            // deletion happened" (the unchanged anchor above the red block).
            const revealModified = (!this.isSideBySide && isDeletion)
                ? Math.max(1, targetModifiedLine + 1)
                : targetModifiedLine;
            modifiedEditor.revealLineInCenter(revealModified);
        }

        if (isDeletion) {
            if (!this.isSideBySide) {
                // Inline: deleted rows are view-zones on modified — decorate via DOM.
                this.highlightInlineDeletedChange(change);
                return;
            }
            this.focusDiffEditorAtLine(originalEditor, targetOriginalLine, 'original', {
                highlightKind: 'deleted',
                endLineNumber: targetOriginalEnd > 0 ? targetOriginalEnd : targetOriginalLine
            });
            return;
        }

        this.focusDiffEditorAtLine(modifiedEditor, targetModifiedLine, 'modified', {
            endLineNumber: targetModifiedEnd > 0 ? targetModifiedEnd : targetModifiedLine
        });
    }

    updateFormatErrorBanner() {
        const banner = document.getElementById('format-error-banner');
        if (!banner) {
            return;
        }

        if (!this.formatError) {
            banner.style.display = 'none';
            banner.textContent = '';
            return;
        }

        banner.style.display = '';
        banner.textContent = this.formatError;
    }

    storageGet(key, fallback = null) {
        try {
            const value = localStorage.getItem(key);
            return value == null ? fallback : value;
        } catch (e) {
            console.warn(`Failed to load ${key} from localStorage:`, e);
            return fallback;
        }
    }

    storageSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (e) {
            console.warn(`Failed to save ${key} to localStorage:`, e);
        }
    }

    saveFormat(format) {
        this.storageSet('config-diff-format', format);
    }

    loadSavedFormat() {
        const savedFormat = this.storageGet('config-diff-format', 'xml');
        if (savedFormat === 'yaml' || savedFormat === 'json' || savedFormat === 'xml') {
            return savedFormat;
        }
        return 'xml';
    }

    saveHideUnchanged(enabled) {
        this.storageSet('config-diff-hide-unchanged', enabled ? '1' : '0');
    }

    loadSavedHideUnchanged() {
        // Default is "show all lines" => hideUnchangedEnabled = false
        return this.storageGet('config-diff-hide-unchanged', '0') === '1';
    }

    saveContextLineCount(value) {
        this.storageSet('config-diff-context-line-count', String(value));
    }

    loadSavedContextLineCount() {
        const stored = this.storageGet('config-diff-context-line-count', null);
        const parsed = stored != null ? parseInt(stored, 10) : NaN;
        if (Number.isNaN(parsed) || parsed < 0) {
            return 5;
        }
        return parsed;
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

    saveTheme(theme) {
        this.storageSet('monaco-editor-theme', theme);
    }

    loadSavedTheme() {
        return this.storageGet('monaco-editor-theme', 'vs') || 'vs';
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
        this.clearChangeNavHighlight();
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

// Expose the editor class on window for easier reuse and testing
if (typeof window !== 'undefined' && !window.ConfigDiffEditor) {
    window.ConfigDiffEditor = ConfigDiffEditor;
}

// Initialize function that handles multiple scenarios
function initializeConfigDiffEditor() {
    // Only initialize if the diff editor container is present
    if (document.getElementById('diff-editor')) {
        new ConfigDiffEditor();
    }
}

// Expose initializer for environments (like tests or bootstrap scripts)
if (typeof window !== 'undefined' && !window.initializeConfigDiffEditor) {
    window.initializeConfigDiffEditor = initializeConfigDiffEditor;
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
