(function (global) {
    function segmentBaseName(segment) {
        const bracket = String(segment).indexOf('[');
        return bracket === -1 ? segment : String(segment).slice(0, bracket);
    }

    function parseScalarNameValue(raw) {
        if (raw == null) {
            return null;
        }
        let value = String(raw).trim();
        if (!value) {
            return null;
        }
        // Drop inline comments when not inside quotes
        if (value[0] !== '"' && value[0] !== "'") {
            const hash = value.indexOf(' #');
            if (hash !== -1) {
                value = value.slice(0, hash).trim();
            }
        }
        if (
            (value.startsWith('"') && value.endsWith('"'))
            || (value.startsWith("'") && value.endsWith("'"))
        ) {
            value = value.slice(1, -1);
        }
        return value || null;
    }

    function buildIndexForContent(yamlContent) {
        if (!yamlContent) {
            return [];
        }

        const lines = yamlContent.split(/\r?\n/);
        const stack = [];
        const paths = [];
        // YAML list-item bodies are indented one step past the "-"; that extra
        // indent must not create a blank path segment after name-folding.
        let listItemIndent = -1;
        let listContentAdjust = 0;

        for (let i = 0; i < lines.length; i += 1) {
            const line = lines[i];
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) {
                paths[i] = stack.slice();
                continue;
            }

            // List item with key: "- name: value" or "- layer3:"
            const listMatch = /^(\s*)- ([^\s:#]+):\s*(.*?)\s*$/.exec(line);
            // Mapping key: "entry:" or "name: value"
            const keyMatch = !listMatch ? /^(\s*)([^\s:#]+):\s*(.*?)\s*$/.exec(line) : null;

            if (!listMatch && !keyMatch) {
                paths[i] = stack.slice();
                continue;
            }

            const indent = (listMatch || keyMatch)[1] || '';
            const indentLen = indent.length;
            const key = listMatch ? listMatch[2] : keyMatch[2];
            const rawValue = listMatch ? listMatch[3] : keyMatch[3];

            if (listItemIndent >= 0 && indentLen <= listItemIndent) {
                listItemIndent = -1;
                listContentAdjust = 0;
            }

            const level = Math.floor(indentLen / 2) - listContentAdjust;

            // Adjust stack to current level (room for this key's parent chain)
            if (level < 0) {
                stack.length = 0;
            } else {
                stack.length = level;
            }

            const nameValue = key === 'name' ? parseScalarNameValue(rawValue) : null;
            if (nameValue !== null && stack.length > 0) {
                // Fold into parent: entry → entry[name=…]; do not push "name"
                const parent = stack[stack.length - 1];
                const base = segmentBaseName(parent);
                stack[stack.length - 1] = `${base}[name=${nameValue}]`;
                paths[i] = stack.slice();
                if (listMatch) {
                    listItemIndent = indentLen;
                    listContentAdjust = 1;
                }
                continue;
            }

            stack.push(key);
            paths[i] = stack.slice();
            if (listMatch) {
                listItemIndent = indentLen;
                listContentAdjust = 1;
            }
        }

        return paths;
    }

    function extractNameAttribute(attrs) {
        const match = /\bname\s*=\s*(?:"([^"]*)"|'([^']*)')/i.exec(attrs || '');
        if (!match) {
            return null;
        }
        return match[1] !== undefined ? match[1] : match[2];
    }

    function segmentForTag(tagName, attrs) {
        const name = extractNameAttribute(attrs);
        if (name !== null) {
            return `${tagName}[name=${name}]`;
        }
        return tagName;
    }

    function buildIndexForXmlContent(xmlContent) {
        if (!xmlContent) {
            return [];
        }

        const lines = xmlContent.split(/\r?\n/);
        const stack = [];
        const paths = [];
        const tagRe = /<\/?[^>]+>/g;

        for (let i = 0; i < lines.length; i += 1) {
            const line = lines[i];
            tagRe.lastIndex = 0;

            const tags = [];
            let tagMatch = tagRe.exec(line);
            while (tagMatch) {
                tags.push(tagMatch[0]);
                tagMatch = tagRe.exec(line);
            }

            if (!tags.length) {
                paths[i] = stack.slice();
                continue;
            }

            let pathSet = false;

            for (let t = 0; t < tags.length; t += 1) {
                const raw = tags[t];

                // Ignore comments, processing instructions, and declarations
                if (raw.startsWith('<!--') || raw.startsWith('<?') || raw.startsWith('<!')) {
                    continue;
                }

                const closeMatch = /^<\/\s*([A-Za-z_][\w:.-]*)\s*>/.exec(raw);
                if (closeMatch) {
                    paths[i] = stack.slice();
                    pathSet = true;
                    if (stack.length) {
                        const tagName = closeMatch[1];
                        const topName = segmentBaseName(stack[stack.length - 1]);
                        if (topName === tagName) {
                            stack.pop();
                        }
                    }
                    continue;
                }

                const selfCloseMatch = /^<\s*([A-Za-z_][\w:.-]*)([^>]*?)\s*\/>/.exec(raw);
                if (selfCloseMatch) {
                    stack.push(segmentForTag(selfCloseMatch[1], selfCloseMatch[2]));
                    paths[i] = stack.slice();
                    pathSet = true;
                    stack.pop();
                    continue;
                }

                const openMatch = /^<\s*([A-Za-z_][\w:.-]*)([^>]*)>/.exec(raw);
                if (openMatch) {
                    stack.push(segmentForTag(openMatch[1], openMatch[2]));
                    paths[i] = stack.slice();
                    pathSet = true;
                }
            }

            if (!pathSet) {
                paths[i] = stack.slice();
            }
        }

        return paths;
    }

    function buildYamlPathIndex(content, originalContent, language) {
        if (!content) {
            return {
                modifiedPaths: [],
                originalPaths: []
            };
        }

        if (language === 'yaml') {
            return {
                modifiedPaths: buildIndexForContent(content),
                originalPaths: buildIndexForContent(originalContent || '')
            };
        }

        if (language === 'xml') {
            return {
                modifiedPaths: buildIndexForXmlContent(content),
                originalPaths: buildIndexForXmlContent(originalContent || '')
            };
        }

        return {
            modifiedPaths: [],
            originalPaths: []
        };
    }

    global.ConfigDiffYamlPath = {
        buildYamlPathIndex,
        // Exposed for unit-style verification / debugging
        buildIndexForContent,
        buildIndexForXmlContent
    };
})(typeof window !== 'undefined' ? window : globalThis);
