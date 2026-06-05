{{/*
Common labels applied to every resource.
*/}}
{{- define "duck-agent.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels for a given component (pass the component name as a string).
Usage: {{ include "duck-agent.selectorLabels" "embeddings" }}
*/}}
{{- define "duck-agent.selectorLabels" -}}
app.kubernetes.io/name: duck-agent
app.kubernetes.io/component: {{ . }}
{{- end }}

{{/*
Full image reference for a service.
Usage: {{ include "duck-agent.image" (dict "registry" .Values.image.registry "repo" .Values.embeddings.image.repository "tag" .Values.embeddings.image.tag) }}
*/}}
{{- define "duck-agent.image" -}}
{{- if .registry -}}
{{ .registry }}/{{ .repo }}:{{ .tag }}
{{- else -}}
{{ .repo }}:{{ .tag }}
{{- end -}}
{{- end }}

{{/*
Namespace shorthand.
*/}}
{{- define "duck-agent.namespace" -}}
{{ .Release.Namespace }}
{{- end }}
