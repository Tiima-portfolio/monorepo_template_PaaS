{{- define "radiator.labels" -}}
app.kubernetes.io/part-of: {{ .root.Chart.Name }}
app.kubernetes.io/name: {{ .root.Chart.Name }}-{{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
{{- end }}

{{- define "radiator.selector" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}-{{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}
