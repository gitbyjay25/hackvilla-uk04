'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ReactFlow, Background, Controls, MiniMap, MarkerType, Position, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';
import Navbar from '@/components/Navbar';

const ANALYSIS_TAKES_UPTO_MINUTES = 10;

const LAYER_ORDER = ['client', 'edge', 'source', 'application', 'async', 'data', 'external', 'generated_strategy', 'generated_design', 'generated_execution', 'generated_validation', 'generated_release', 'generated'];

const NODE_COLORS = {
    client: '#ffe9b5',
    edge: '#d9e8ff',
    source: '#fef3c7',
    application: '#dcfce7',
    async: '#fce7f3',
    data: '#fae8ff',
    external: '#e0f2fe',
    generated_strategy: '#fee2e2',
    generated_design: '#fde68a',
    generated_execution: '#bfdbfe',
    generated_validation: '#c7d2fe',
    generated_release: '#bbf7d0',
    generated: '#fee2e2',
};

function toSlug(value) {
    return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'node';
}

function humanizeRepoName(fullName) {
    const repo = String(fullName || '').split('/').pop() || 'Repository';
    return repo
        .split(/[_\-]+/g)
        .filter(Boolean)
        .map((part) => part[0].toUpperCase() + part.slice(1))
        .join(' ');
}

function formatUsd(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return 'N/A';
    return `$${amount.toFixed(2)}`;
}

function classifyChangeKind(changeText) {
    const value = String(changeText || '').toLowerCase();
    if (/(queue|event|async|worker|stream)/.test(value)) return 'async';
    if (/(cache|database|data|query|read|write|storage|redis|postgres|mongo)/.test(value)) return 'data';
    if (/(api|gateway|route|endpoint|contract|service boundary)/.test(value)) return 'api';
    if (/(test|qa|quality|validate|verification|regression)/.test(value)) return 'quality';
    if (/(observability|trace|metric|alert|monitor)/.test(value)) return 'observability';
    if (/(security|auth|oauth|token|permission|rbac)/.test(value)) return 'security';
    if (/(performance|latency|throughput|optimi)/.test(value)) return 'performance';
    if (/(cost|efficien|consolidat|shared)/.test(value)) return 'cost';
    if (/(scale|scalability|shard|partition|autoscal)/.test(value)) return 'scalability';
    return 'architecture';
}

function layerForChangeKind(kind) {
    if (['api', 'security', 'architecture'].includes(kind)) return 'generated_design';
    if (['quality', 'observability'].includes(kind)) return 'generated_validation';
    return 'generated_execution';
}

function pickTargetsForChange(changeText, baseNodes, impactedNodeIds) {
    const tokens = Array.from(
        new Set(
            String(changeText || '')
                .toLowerCase()
                .split(/[^a-z0-9]+/g)
                .filter((token) => token.length >= 4),
        ),
    );

    const directMatches = baseNodes
        .filter((node) => !String(node.id).startsWith('generated_'))
        .filter((node) => {
            const haystack = `${node.label || ''} ${node.id || ''} ${node.kind || ''}`.toLowerCase();
            return tokens.some((token) => haystack.includes(token));
        })
        .map((node) => node.id);

    if (directMatches.length) {
        return directMatches.slice(0, 4);
    }

    const impacted = Array.from(impactedNodeIds || []).slice(0, 4);
    if (impacted.length) {
        return impacted;
    }

    return baseNodes
        .filter((node) => ['runtime_service', 'static_service', 'app_service', 'database', 'queue', 'cache'].includes(node.kind))
        .map((node) => node.id)
        .slice(0, 4);
}

function normalizeArchitectureSketchGraph(graph) {
    const baseGraph = graph || {};
    const nodes = graph?.nodes || [];
    const edges = graph?.edges || [];
    const repoDisplay = humanizeRepoName(graph?.repository?.full_name);

    const hasClient = nodes.some((node) => node.layer === 'client' || node.id === 'client');
    const hasGateway = nodes.some((node) => node.id === 'api_gateway');
    const hasRepoSpecificService = nodes.some(
        (node) => ['runtime_service', 'static_service'].includes(node.kind)
            || (node.kind === 'app_service' && node.id !== 'app_core'),
    );

    // If backend already returns architecture-flow graph, use as-is.
    if (hasClient && hasGateway && hasRepoSpecificService) {
        return graph;
    }

    const runtimeNodes = nodes.filter((node) => node.kind === 'runtime_service' || String(node.id || '').startsWith('svc_'));
    const dbNodes = nodes.filter((node) => node.kind === 'database_signal' || String(node.id || '').startsWith('db_'));
    const depNodes = nodes.filter((node) => node.kind === 'dependency_manifest' || String(node.id || '').startsWith('dep_'));

    const depText = depNodes.map((n) => String(n.label || '').toLowerCase()).join(' ');
    const hasQueue = /(kafka|rabbit|sqs|celery)/.test(depText);
    const hasCache = /(redis|memcache)/.test(depText);
    const hasExternal = /(stripe|twilio|sendgrid|httpx|requests)/.test(depText);

    const flowNodes = [
        { id: 'client', label: `${repoDisplay} Client Applications`, layer: 'client', kind: 'entrypoint', meta: {} },
        { id: 'edge', label: 'Edge / Load Balancer', layer: 'edge', kind: 'ingress', meta: {} },
        { id: 'api_gateway', label: `${repoDisplay} API Gateway`, layer: 'application', kind: 'gateway', meta: {} },
    ];
    const flowEdges = [
        { id: 'edge_client_edge', source: 'client', target: 'edge', type: 'https', meta: {} },
        { id: 'edge_edge_api_gateway', source: 'edge', target: 'api_gateway', type: 'routes', meta: {} },
    ];

    const serviceNodes = runtimeNodes.length
        ? runtimeNodes.slice(0, 12).map((node) => ({
            id: node.id,
            label: node.label,
            layer: 'application',
            kind: node.kind || 'runtime_service',
            meta: node.meta || {},
        }))
        : [{ id: 'app_core', label: `${repoDisplay} Core Service`, layer: 'application', kind: 'app_service', meta: {} }];

    for (const service of serviceNodes) {
        flowNodes.push(service);
        flowEdges.push({ id: `edge_api_gateway_${service.id}`, source: 'api_gateway', target: service.id, type: 'calls', meta: {} });
    }

    if (hasQueue) {
        flowNodes.push({ id: 'async_queue', label: 'Async Queue / Event Bus', layer: 'async', kind: 'queue', meta: {} });
        flowNodes.push({ id: 'worker_pool', label: 'Worker Pool', layer: 'async', kind: 'workers', meta: {} });
        for (const service of serviceNodes) {
            flowEdges.push({ id: `edge_${service.id}_async_queue`, source: service.id, target: 'async_queue', type: 'publishes', meta: {} });
        }
        flowEdges.push({ id: 'edge_async_queue_worker_pool', source: 'async_queue', target: 'worker_pool', type: 'consumes', meta: {} });
    }

    if (hasCache) {
        flowNodes.push({ id: 'cache_layer', label: 'Cache Layer', layer: 'data', kind: 'cache', meta: {} });
        for (const service of serviceNodes) {
            flowEdges.push({ id: `edge_${service.id}_cache_layer`, source: service.id, target: 'cache_layer', type: 'reads_writes', meta: {} });
        }
    }

    if (dbNodes.length) {
        flowNodes.push({
            id: 'primary_data_store',
            label: 'Primary Data Store',
            layer: 'data',
            kind: 'database',
            meta: { database_signal_count: dbNodes.length },
        });
        for (const service of serviceNodes) {
            flowEdges.push({ id: `edge_${service.id}_primary_data_store`, source: service.id, target: 'primary_data_store', type: 'queries', meta: {} });
        }
    }

    if (hasExternal) {
        flowNodes.push({ id: 'external_integrations', label: 'External Integrations', layer: 'external', kind: 'external_api', meta: {} });
        for (const service of serviceNodes.slice(0, 4)) {
            flowEdges.push({ id: `edge_${service.id}_external_integrations`, source: service.id, target: 'external_integrations', type: 'calls', meta: {} });
        }
    }

    return {
        ...baseGraph,
        nodes: flowNodes,
        edges: flowEdges,
        layers: ['client', 'edge', 'application', 'async', 'data', 'external'],
        normalized_from_legacy_graph: true,
    };
}

function inferImpactedNodeIdsForVariant(variant, graph) {
    const impacted = new Set();
    const changes = variant?.variant?.major_changes || [];
    const keywords = Array.from(
        new Set(
            changes
                .flatMap((change) => String(change).toLowerCase().split(/[^a-z0-9]+/g))
                .filter((token) => token.length >= 4),
        ),
    );

    if (!keywords.length) {
        return impacted;
    }

    for (const node of graph?.nodes || []) {
        const haystack = `${node?.label || ''} ${node?.id || ''} ${node?.kind || ''}`.toLowerCase();
        if (keywords.some((keyword) => haystack.includes(keyword))) {
            impacted.add(node.id);
        }
    }

    return impacted;
}

function layoutGraphToFlow(graph, impactedNodeIds = new Set()) {
    const edgeList = graph?.edges || [];
    const incomingByTarget = new Map();
    for (const edge of edgeList) {
        if (!incomingByTarget.has(edge.target)) {
            incomingByTarget.set(edge.target, []);
        }
        incomingByTarget.get(edge.target).push(edge.source);
    }

    const layerBuckets = {};
    for (const node of graph?.nodes || []) {
        const layer = node.layer || 'application';
        if (!layerBuckets[layer]) {
            layerBuckets[layer] = [];
        }
        layerBuckets[layer].push(node);
    }

    const layers = Object.keys(layerBuckets).sort((a, b) => {
        const ai = LAYER_ORDER.indexOf(a);
        const bi = LAYER_ORDER.indexOf(b);
        return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

    // Reorder nodes inside each layer based on upstream neighbors to reduce crossings.
    const orderIndexByLayer = new Map();
    layers.forEach((layer, layerIndex) => {
        const bucket = [...(layerBuckets[layer] || [])];
        if (!layerIndex) {
            bucket.sort((a, b) => String(a.label || a.id).localeCompare(String(b.label || b.id)));
        } else {
            const prevLayer = layers[layerIndex - 1];
            const prevOrder = orderIndexByLayer.get(prevLayer) || new Map();
            bucket.sort((a, b) => {
                const aSources = incomingByTarget.get(a.id) || [];
                const bSources = incomingByTarget.get(b.id) || [];
                const avg = (sources) => {
                    const matched = sources
                        .map((sid) => prevOrder.get(sid))
                        .filter((value) => value !== undefined);
                    if (!matched.length) return Number.MAX_SAFE_INTEGER;
                    return matched.reduce((sum, value) => sum + value, 0) / matched.length;
                };
                const diff = avg(aSources) - avg(bSources);
                if (diff !== 0) return diff;
                return String(a.label || a.id).localeCompare(String(b.label || b.id));
            });
        }
        layerBuckets[layer] = bucket;
        const indexMap = new Map();
        bucket.forEach((node, idx) => indexMap.set(node.id, idx));
        orderIndexByLayer.set(layer, indexMap);
    });

    const maxNodesInLayer = Math.max(1, ...layers.map((layer) => (layerBuckets[layer] || []).length));
    const layerSpacing = 300;
    const rowSpacing = 100;
    const canvasTop = 80;
    const canvasHeight = Math.max(520, maxNodesInLayer * rowSpacing + 80);

    const nodes = [];
    layers.forEach((layer, layerIndex) => {
        const bucket = layerBuckets[layer] || [];
        const layerHeight = Math.max(0, (bucket.length - 1) * rowSpacing);
        const layerTop = canvasTop + Math.max(0, (canvasHeight - layerHeight) / 2 - 40);
        bucket.forEach((node, nodeIndex) => {
            const impacted = impactedNodeIds.has(node.id);
            nodes.push({
                id: node.id,
                position: {
                    x: 120 + layerIndex * layerSpacing,
                    y: layerTop + nodeIndex * rowSpacing,
                },
                data: {
                    label: `${node.label}`,
                },
                sourcePosition: Position.Right,
                targetPosition: Position.Left,
                style: {
                    width: 220,
                    borderRadius: 12,
                    border: impacted ? '3px solid #0056d6' : '2px solid #1f2937',
                    background: impacted ? '#eff6ff' : (NODE_COLORS[layer] || '#f3f4f6'),
                    fontSize: 12,
                    fontWeight: 600,
                    padding: 10,
                },
            });
        });
    });

    const showLabels = edgeList.length <= 40;
    const edges = edgeList.map((edge) => {
        const highlighted = impactedNodeIds.has(edge.source) || impactedNodeIds.has(edge.target);
        return {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            animated: highlighted,
            type: 'smoothstep',
            label: highlighted || showLabels ? (edge.type || '') : '',
            markerEnd: { type: MarkerType.ArrowClosed },
            pathOptions: { offset: 18, borderRadius: 14 },
            style: {
                stroke: highlighted ? '#0056d6' : '#475569',
                strokeWidth: highlighted ? 3 : 2,
                strokeOpacity: highlighted ? 1 : 0.8,
            },
            labelStyle: { fontSize: 11, fontWeight: 600 },
        };
    });

    return { nodes, edges };
}

function buildGeneratedVariantGraph(baseGraph, variant, impactedNodeIds) {
    const baseNodes = (baseGraph?.nodes || []).map((node) => ({ ...node }));
    const baseEdges = (baseGraph?.edges || []).map((edge) => ({ ...edge }));
    const targetProfile = String(variant?.variant?.target_profile || '').toLowerCase();
    const repoDisplay = humanizeRepoName(baseGraph?.repository?.full_name);
    const workflowNodeId = `generated_workflow_${variant.id}`;
    const discoveryNodeId = `generated_discovery_${variant.id}`;
    const plannerNodeId = `generated_planner_${variant.id}`;
    const apiDesignNodeId = `generated_api_design_${variant.id}`;
    const runtimeNodeId = `generated_runtime_${variant.id}`;
    const observabilityNodeId = `generated_observability_${variant.id}`;
    const qaGateNodeId = `generated_qa_gate_${variant.id}`;
    const rolloutNodeId = `generated_rollout_${variant.id}`;
    const asyncNodeId = `generated_async_${variant.id}`;
    const dataNodeId = `generated_data_${variant.id}`;
    const edgeNodeId = `generated_edge_${variant.id}`;
    const securityNodeId = `generated_security_${variant.id}`;
    const changes = variant?.variant?.major_changes || [];

    baseNodes.push(
        {
            id: workflowNodeId,
            label: `${repoDisplay}: ${variant.title} Deep Workflow`,
            layer: 'generated_strategy',
            kind: 'generated_workflow',
            meta: { summary: (variant?.variant?.major_changes || []).join(' | ') },
        },
        {
            id: discoveryNodeId,
            label: `${repoDisplay} Repository + Runtime Discovery`,
            layer: 'generated_strategy',
            kind: 'generated_discovery',
            meta: {},
        },
        {
            id: plannerNodeId,
            label: 'Deep Planner / Architecture Optimizer',
            layer: 'generated_strategy',
            kind: 'generated_planner',
            meta: { target_profile: targetProfile || 'balanced' },
        },
        {
            id: apiDesignNodeId,
            label: 'API Contract & Service Boundary Design',
            layer: 'generated_design',
            kind: 'generated_api_design',
            meta: {},
        },
        {
            id: runtimeNodeId,
            label: targetProfile === 'performance' ? 'Low-Latency Runtime Path' : targetProfile === 'cost' ? 'Shared Runtime Path' : 'Scalable Runtime Path',
            layer: 'generated_execution',
            kind: 'generated_runtime',
            meta: {},
        },
        {
            id: observabilityNodeId,
            label: 'Tracing + Metrics + Alerting Layer',
            layer: 'generated_validation',
            kind: 'generated_observability',
            meta: {},
        },
        {
            id: qaGateNodeId,
            label: 'Test & Quality Gates',
            layer: 'generated_validation',
            kind: 'generated_quality_gate',
            meta: {},
        },
        {
            id: rolloutNodeId,
            label: 'Canary Rollout & Progressive Delivery',
            layer: 'generated_release',
            kind: 'generated_rollout',
            meta: {},
        },
        {
            id: securityNodeId,
            label: 'Security & Policy Hardening',
            layer: 'generated_design',
            kind: 'generated_security',
            meta: {},
        },
    );

    baseEdges.push(
        { id: `${workflowNodeId}_${discoveryNodeId}`, source: workflowNodeId, target: discoveryNodeId, type: 'starts', meta: { generated: true } },
        { id: `${discoveryNodeId}_${plannerNodeId}`, source: discoveryNodeId, target: plannerNodeId, type: 'analyzes', meta: { generated: true } },
        { id: `${plannerNodeId}_${apiDesignNodeId}`, source: plannerNodeId, target: apiDesignNodeId, type: 'designs', meta: { generated: true } },
        { id: `${plannerNodeId}_${securityNodeId}`, source: plannerNodeId, target: securityNodeId, type: 'hardens', meta: { generated: true } },
        { id: `${apiDesignNodeId}_${runtimeNodeId}`, source: apiDesignNodeId, target: runtimeNodeId, type: 'implements', meta: { generated: true } },
        { id: `${securityNodeId}_${runtimeNodeId}`, source: securityNodeId, target: runtimeNodeId, type: 'guards', meta: { generated: true } },
        { id: `${runtimeNodeId}_${observabilityNodeId}`, source: runtimeNodeId, target: observabilityNodeId, type: 'observes', meta: { generated: true } },
        { id: `${observabilityNodeId}_${qaGateNodeId}`, source: observabilityNodeId, target: qaGateNodeId, type: 'validates', meta: { generated: true } },
        { id: `${qaGateNodeId}_${rolloutNodeId}`, source: qaGateNodeId, target: rolloutNodeId, type: 'releases', meta: { generated: true } },
    );

    changes.slice(0, 10).forEach((change, idx) => {
        const changeKind = classifyChangeKind(change);
        const changeNodeId = `generated_change_${variant.id}_${toSlug(change)}_${idx + 1}`;
        const changeLayer = layerForChangeKind(changeKind);
        const parentNodeId = changeLayer === 'generated_design'
            ? apiDesignNodeId
            : changeLayer === 'generated_validation'
                ? observabilityNodeId
                : runtimeNodeId;

        baseNodes.push({
            id: changeNodeId,
            label: `${idx + 1}. ${change}`,
            layer: changeLayer,
            kind: `generated_change_${changeKind}`,
            meta: { change_kind: changeKind },
        });
        baseEdges.push({
            id: `${parentNodeId}_${changeNodeId}`,
            source: parentNodeId,
            target: changeNodeId,
            type: 'implements',
            meta: { generated: true, from_change: true },
        });

        pickTargetsForChange(change, baseNodes, impactedNodeIds)
            .slice(0, 4)
            .forEach((targetId, targetIdx) => {
                baseEdges.push({
                    id: `${changeNodeId}_touches_${targetId}_${targetIdx + 1}`,
                    source: changeNodeId,
                    target: targetId,
                    type: 'touches',
                    meta: { generated: true, from_change: true },
                });
            });
    });

    if (targetProfile === 'performance') {
        baseNodes.push({
            id: edgeNodeId,
            label: 'Edge Optimization (CDN + Route Caching)',
            layer: 'generated_execution',
            kind: 'generated_edge_opt',
            meta: {},
        });
        baseEdges.push({ id: `${apiDesignNodeId}_${edgeNodeId}`, source: apiDesignNodeId, target: edgeNodeId, type: 'accelerates', meta: { generated: true } });
        baseEdges.push({ id: `${edgeNodeId}_${runtimeNodeId}`, source: edgeNodeId, target: runtimeNodeId, type: 'serves', meta: { generated: true } });
    }

    if (targetProfile === 'scalability' || targetProfile === 'performance') {
        baseNodes.push({
            id: asyncNodeId,
            label: targetProfile === 'scalability' ? 'Queue + Worker Expansion' : 'Async Critical Path Offload',
            layer: 'generated_execution',
            kind: 'generated_async',
            meta: {},
        });
        baseEdges.push({ id: `${runtimeNodeId}_${asyncNodeId}`, source: runtimeNodeId, target: asyncNodeId, type: 'offloads', meta: { generated: true } });
    }

    if (targetProfile === 'cost' || targetProfile === 'performance') {
        baseNodes.push({
            id: dataNodeId,
            label: targetProfile === 'cost' ? 'Cost-Aware Data Access Layer' : 'Hot Path Data Optimization',
            layer: 'generated_execution',
            kind: 'generated_data',
            meta: {},
        });
        baseEdges.push({ id: `${runtimeNodeId}_${dataNodeId}`, source: runtimeNodeId, target: dataNodeId, type: 'optimizes', meta: { generated: true } });
    }

    const targets = Array.from(impactedNodeIds);
    const fallbackTargets = baseNodes
        .filter((node) => ['api_gateway', 'app_core', 'primary_data_store', 'cache_layer', 'async_queue'].includes(node.id))
        .map((node) => node.id);
    const selectedTargets = targets.length ? targets : fallbackTargets;
    selectedTargets.slice(0, 10).forEach((targetId, idx) => {
        baseEdges.push({
            id: `${runtimeNodeId}_integration_${idx}`,
            source: runtimeNodeId,
            target: targetId,
            type: 'integrates',
            meta: { generated: true },
        });
    });

    return {
        ...baseGraph,
        nodes: baseNodes,
        edges: baseEdges,
        layers: Array.from(new Set([...(baseGraph?.layers || []), 'generated_strategy', 'generated_design', 'generated_execution', 'generated_validation', 'generated_release', 'generated'])),
    };
}

function createFallbackBaseGraph() {
    return {
        version: '1.0',
        nodes: [
            { id: 'client', label: 'Client / Frontend', layer: 'client', kind: 'entrypoint', meta: {} },
            { id: 'edge', label: 'Edge / Load Balancer', layer: 'edge', kind: 'ingress', meta: {} },
            { id: 'api_gateway', label: 'API Gateway', layer: 'application', kind: 'gateway', meta: {} },
            { id: 'app_core', label: 'Core Application Service', layer: 'application', kind: 'app_service', meta: {} },
            { id: 'primary_data_store', label: 'Primary Data Store', layer: 'data', kind: 'database', meta: {} },
        ],
        edges: [
            { id: 'edge_client_edge', source: 'client', target: 'edge', type: 'https', meta: {} },
            { id: 'edge_edge_api_gateway', source: 'edge', target: 'api_gateway', type: 'routes', meta: {} },
            { id: 'edge_api_gateway_app_core', source: 'api_gateway', target: 'app_core', type: 'calls', meta: {} },
            { id: 'edge_app_core_primary_data_store', source: 'app_core', target: 'primary_data_store', type: 'queries', meta: {} },
        ],
        layers: ['client', 'edge', 'application', 'data'],
        layout_hint: '2d-layered',
    };
}

export default function SystemArchitecturePage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [githubInstallations, setGithubInstallations] = useState([]);
    const [installations, setInstallations] = useState([]);
    const [repositories, setRepositories] = useState([]);
    const [documents, setDocuments] = useState([]);
    const [variants, setVariants] = useState([]);
    const [architectureGraph, setArchitectureGraph] = useState(null);
    const [graphLoading, setGraphLoading] = useState(false);
    const [graphError, setGraphError] = useState('');
    const [diffVariantId, setDiffVariantId] = useState('');
    const [activeWorkflowVariantId, setActiveWorkflowVariantId] = useState('');
    const [generatedWorkflowGraphs, setGeneratedWorkflowGraphs] = useState({});
    const [workflowModal, setWorkflowModal] = useState({ open: false, type: 'original', variantId: '' });
    const [selectedRepositoryId, setSelectedRepositoryId] = useState('');
    const [selectedSnapshotId, setSelectedSnapshotId] = useState('');
    const [sdkApps, setSdkApps] = useState([]);
    const [selectedSdkAppSelector, setSelectedSdkAppSelector] = useState('');
    const [selectedDocumentId, setSelectedDocumentId] = useState('');
    const [historyOpen, setHistoryOpen] = useState(false);
    const [historyQuery, setHistoryQuery] = useState('');
    const [weightCost, setWeightCost] = useState(30);
    const [weightScalability, setWeightScalability] = useState(35);
    const [weightPerformance, setWeightPerformance] = useState(35);
    const [loading, setLoading] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisElapsedSec, setAnalysisElapsedSec] = useState(0);
    const [analysisAttempt, setAnalysisAttempt] = useState(0);
    const [reportJobsByVariantId, setReportJobsByVariantId] = useState({});
    const [reportBusyByVariantId, setReportBusyByVariantId] = useState({});
    const [reportErrorByVariantId, setReportErrorByVariantId] = useState({});
    const [analysisEmailNotification, setAnalysisEmailNotification] = useState(null);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [originalNodes, setOriginalNodes, onOriginalNodesChange] = useNodesState([]);
    const [originalEdges, setOriginalEdges, onOriginalEdgesChange] = useEdgesState([]);
    const [generatedNodes, setGeneratedNodes, onGeneratedNodesChange] = useNodesState([]);
    const [generatedEdges, setGeneratedEdges, onGeneratedEdgesChange] = useEdgesState([]);

    const clampWeight = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));

    useEffect(() => {
        if (!analyzing) {
            setAnalysisElapsedSec(0);
            return;
        }

        const startedAt = Date.now();
        const timer = setInterval(() => {
            setAnalysisElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
        }, 1000);

        return () => clearInterval(timer);
    }, [analyzing]);

    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    const triggerBrowserDownload = (blob, filename) => {
        if (typeof window === 'undefined') {
            return;
        }

        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = objectUrl;
        anchor.download = filename || 'workflow_report.pdf';
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(objectUrl);
    };

    const pollWorkflowReportUntilDone = async (reportId, timeoutMs = 240000) => {
        const started = Date.now();
        while (Date.now() - started < timeoutMs) {
            const status = await apiClient.getVariantWorkflowReport(reportId);
            if (status?.status === 'completed' || status?.status === 'failed') {
                return status;
            }
            await wait(2500);
        }
        throw new Error('Workflow report generation timed out. Please retry.');
    };

    const analysisStatusText = useMemo(() => {
        if (analysisElapsedSec < 20) {
            return 'Preparing repository context and validating snapshot';
        }
        if (analysisElapsedSec < 55) {
            return 'Running deep architecture extraction and dependency mapping';
        }
        if (analysisElapsedSec < 95) {
            return 'Computing architecture variants based on optimization weights';
        }
        return 'Finalizing architecture artifacts and writing outputs';
    }, [analysisElapsedSec]);

    const filteredHistoryDocuments = useMemo(() => {
        const query = String(historyQuery || '').trim().toLowerCase();
        if (!query) {
            return documents || [];
        }
        return (documents || []).filter((doc) => {
            const key = String(doc.unique_key || '').toLowerCase();
            const repoId = String(doc.repository_id || '').toLowerCase();
            const snapshotId = String(doc.snapshot_id || '').toLowerCase();
            return key.includes(query) || repoId.includes(query) || snapshotId.includes(query);
        });
    }, [documents, historyQuery]);

    const selectedSdkApp = useMemo(
        () => sdkApps.find((item) => item.selector_value === selectedSdkAppSelector) || null,
        [sdkApps, selectedSdkAppSelector],
    );

    const selectedVariantForDiff = useMemo(
        () => variants.find((variant) => variant.id === diffVariantId) || null,
        [variants, diffVariantId],
    );

    const diffKeywords = useMemo(() => {
        const changes = selectedVariantForDiff?.variant?.major_changes || [];
        const tokens = changes
            .flatMap((change) => String(change).toLowerCase().split(/[^a-z0-9]+/g))
            .filter((token) => token.length >= 4);
        return Array.from(new Set(tokens));
    }, [selectedVariantForDiff]);

    const impactedNodeIds = useMemo(() => {
        const impacted = new Set();
        const nodes = architectureGraph?.nodes || [];
        if (!nodes.length || !diffKeywords.length) {
            return impacted;
        }

        for (const node of nodes) {
            const haystack = `${node?.label || ''} ${node?.id || ''}`.toLowerCase();
            if (diffKeywords.some((keyword) => haystack.includes(keyword))) {
                impacted.add(node.id);
            }
        }
        return impacted;
    }, [architectureGraph, diffKeywords]);

    const highlightedEdgeIds = useMemo(() => {
        const highlighted = new Set();
        for (const edge of architectureGraph?.edges || []) {
            if (impactedNodeIds.has(edge.source) || impactedNodeIds.has(edge.target)) {
                highlighted.add(edge.id);
            }
        }
        return highlighted;
    }, [architectureGraph, impactedNodeIds]);

    const originalFlow = useMemo(() => {
        if (!architectureGraph) {
            return { nodes: [], edges: [] };
        }
        return layoutGraphToFlow(architectureGraph, impactedNodeIds);
    }, [architectureGraph, impactedNodeIds]);

    const modalVariantId = workflowModal.variantId || activeWorkflowVariantId;
    const activeGeneratedGraph = generatedWorkflowGraphs[modalVariantId] || null;
    const activeWorkflowVariant = useMemo(
        () => variants.find((variant) => variant.id === modalVariantId) || null,
        [variants, modalVariantId],
    );

    const generatedFlow = useMemo(() => {
        if (!activeGeneratedGraph) {
            return { nodes: [], edges: [] };
        }
        const impacted = activeWorkflowVariant ? inferImpactedNodeIdsForVariant(activeWorkflowVariant, architectureGraph || {}) : new Set();
        return layoutGraphToFlow(activeGeneratedGraph, impacted);
    }, [activeGeneratedGraph, activeWorkflowVariant, architectureGraph]);

    useEffect(() => {
        setOriginalNodes(originalFlow.nodes || []);
        setOriginalEdges(originalFlow.edges || []);
    }, [originalFlow, setOriginalNodes, setOriginalEdges]);

    useEffect(() => {
        setGeneratedNodes(generatedFlow.nodes || []);
        setGeneratedEdges(generatedFlow.edges || []);
    }, [generatedFlow, setGeneratedNodes, setGeneratedEdges]);

    const hasGithubConnected = githubInstallations.length > 0;

    const loadDocumentContext = async (documentId) => {
        if (!documentId) {
            setVariants([]);
            setArchitectureGraph(null);
            setDiffVariantId('');
            setActiveWorkflowVariantId('');
            setGeneratedWorkflowGraphs({});
            setWorkflowModal({ open: false, type: 'original', variantId: '' });
            return;
        }

        setGraphLoading(true);
        setGraphError('');
        try {
            const [variantRows, graph] = await Promise.all([
                apiClient.listArchitectureVariants(documentId),
                apiClient.getArchitectureGraphJson(documentId),
            ]);
            setVariants(variantRows || []);
            setArchitectureGraph(normalizeArchitectureSketchGraph(graph || null));
            setGeneratedWorkflowGraphs({});
            setActiveWorkflowVariantId('');
            setWorkflowModal({ open: false, type: 'original', variantId: '' });
            if ((variantRows || []).length && !diffVariantId) {
                setDiffVariantId(variantRows[0].id);
            }
        } catch (err) {
            setArchitectureGraph(null);
            setGraphError(err.message || 'Failed to load architecture graph JSON');
        } finally {
            setGraphLoading(false);
        }
    };

    const importRepositoriesFromInstallation = async (installationRow) => {
        const response = await apiClient.listInstallationRepositories(installationRow.id);
        const installationRepos = response?.repositories || [];

        if (!installationRepos.length) {
            setMessage('No repositories were returned by GitHub for this installation. Check installation scope and repository access.');
            return [];
        }

        const connectPayloads = installationRepos.map((repo) => {
            const [owner, repoName] = String(repo.full_name || '').split('/');
            return {
                installation_id: installationRow.id,
                owner: owner || repo.owner,
                repo_name: repoName || repo.name,
                default_branch: repo.default_branch || 'main',
                is_private: Boolean(repo.private),
                is_monorepo: true,
                remote_url: repo.clone_url || null,
                local_repo_path: null,
            };
        }).filter((payload) => payload.owner && payload.repo_name);

        if (!connectPayloads.length) {
            setError('No valid repositories found to connect.');
            return [];
        }

        await Promise.all(connectPayloads.map((payload) => apiClient.connectRepository(payload)));
        const connectedRepos = await apiClient.listConnectedRepositories();
        setRepositories(connectedRepos || []);
        return connectedRepos || [];
    };

    const fetchAll = async (preferredDocumentId = null) => {
        setLoading(true);
        setError('');
        try {
            const [inst, repos, docs, sdkAppsPayload] = await Promise.all([
                apiClient.listGithubInstallations(),
                apiClient.listConnectedRepositories(),
                apiClient.listArchitectureDocuments(),
                apiClient.listSdkApps(),
            ]);
            setGithubInstallations(inst || []);
            setInstallations(inst || []);
            setSdkApps((sdkAppsPayload && sdkAppsPayload.apps) ? sdkAppsPayload.apps : []);
            let connectedRepos = repos || [];

            // Auto-sync repositories from the first GitHub installation if tenant has
            // an installation but no connected repositories yet.
            if ((inst || []).length && !connectedRepos.length) {
                try {
                    connectedRepos = await importRepositoriesFromInstallation(inst[0]);
                    if (connectedRepos.length) {
                        setMessage('Repositories synced from your GitHub installation.');
                    }
                } catch (syncErr) {
                    console.error('Repository sync failed:', syncErr);
                }
            }

            setRepositories(connectedRepos);
            setDocuments(docs || []);
            const targetDocumentId = preferredDocumentId || selectedDocumentId;
            const hasSelectedDoc = Boolean(
                targetDocumentId && (docs || []).some((doc) => doc.id === targetDocumentId),
            );
            if (!hasSelectedDoc) {
                setSelectedDocumentId('');
                setVariants([]);
                setArchitectureGraph(null);
                setDiffVariantId('');
                setActiveWorkflowVariantId('');
                setGeneratedWorkflowGraphs({});
                setWorkflowModal({ open: false, type: 'original', variantId: '' });
            } else if (targetDocumentId !== selectedDocumentId) {
                setSelectedDocumentId(targetDocumentId);
            }
        } catch (err) {
            setError(err.message || 'Failed to load System-Architecture data');
        } finally {
            setLoading(false);
        }
    };

    const syncRepositories = async () => {
        if (!installations.length) {
            setError('No GitHub installation found to sync repositories from.');
            return;
        }

        setLoading(true);
        setError('');
        setMessage('');
        try {
            const connectedRepos = await importRepositoriesFromInstallation(installations[0]);
            if (connectedRepos.length) {
                setMessage(`Synced ${connectedRepos.length} connected repositories from GitHub.`);
            }
        } catch (err) {
            setError(err.message || 'Failed to sync repositories from GitHub installation.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!authLoading && isAuthenticated) {
            fetchAll();
        }
    }, [authLoading, isAuthenticated]);

    useEffect(() => {
        if (!authLoading && isAuthenticated && selectedDocumentId) {
            loadDocumentContext(selectedDocumentId);
        }
    }, [authLoading, isAuthenticated, selectedDocumentId]);

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }

        const params = new URLSearchParams(window.location.search);
        const installationId = params.get('installation_id');
        const setupAction = params.get('setup_action');
        const variantFocus = params.get('variant');

        if (variantFocus) {
            setDiffVariantId(variantFocus);
        }

        if (!installationId || !isAuthenticated || authLoading) {
            return;
        }

        if (setupAction && setupAction !== 'install' && setupAction !== 'update') {
            return;
        }

        const completeInstall = async () => {
            setLoading(true);
            setError('');
            try {
                await apiClient.autoLinkGithubInstallation(installationId);
                setMessage('GitHub installation linked successfully.');
                await fetchAll();
                router.replace('/system-architecture');
            } catch (err) {
                setError(err.message || 'Failed to auto-link GitHub installation. Please complete linking from Profile.');
            } finally {
                setLoading(false);
            }
        };

        completeInstall();
    }, [isAuthenticated, authLoading, router]);

    const createSnapshot = async () => {
        if (!hasGithubConnected) {
            setError('GitHub account is not connected. Redirecting to Profile page...');
            setTimeout(() => router.push('/profile'), 1200);
            return;
        }
        if (!selectedRepositoryId) {
            setError('Select a connected repository first.');
            return;
        }
        setLoading(true);
        setError('');
        setMessage('');
        try {
            const result = await apiClient.createRepositorySnapshot(selectedRepositoryId, {
                use_default_branch: true,
            });
            if (result?.status !== 'created') {
                setSelectedSnapshotId('');
                setError(result?.message || `Snapshot failed: ${result?.status || 'unknown error'}`);
                return;
            }
            setSelectedSnapshotId(result.snapshot_id);
            setMessage(`Snapshot created: ${result.snapshot_id}`);
        } catch (err) {
            setSelectedSnapshotId('');
            setError(err.message || 'Failed to create snapshot');
        } finally {
            setLoading(false);
        }
    };

    const analyzeAndGenerate = async () => {
        if (!hasGithubConnected) {
            setError('GitHub account is not connected. Redirecting to Profile page...');
            setTimeout(() => router.push('/profile'), 1200);
            return;
        }
        if (!selectedRepositoryId || !selectedSnapshotId) {
            setError('Create a snapshot first.');
            return;
        }
        setLoading(true);
        setAnalyzing(true);
        setAnalysisAttempt(0);
        setAnalysisEmailNotification(null);
        setError('');
        setMessage('Analyzing repository and generating architecture variants. You will receive an email notification when it completes.');
        try {
            const payload = {
                snapshot_id: selectedSnapshotId,
                mode: 'auto',
                telemetry_project_id: selectedSdkApp?.telemetry_project_id || null,
                telemetry_service_name: selectedSdkApp?.telemetry_service_name || null,
                cost_weight: Number(weightCost),
                scalability_weight: Number(weightScalability),
                performance_weight: Number(weightPerformance),
            };

            let result = null;
            const maxAttempts = 2;
            for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
                setAnalysisAttempt(attempt);
                try {
                    result = await apiClient.analyzeRepository(selectedRepositoryId, payload);
                    break;
                } catch (attemptErr) {
                    const errText = String(attemptErr?.message || '').toLowerCase();
                    const isTransientGateway = errText.includes('502') || errText.includes('bad gateway');
                    if (!isTransientGateway || attempt === maxAttempts) {
                        throw attemptErr;
                    }
                    setMessage('Analysis backend is warming up. Retrying automatically...');
                    await wait(3000);
                }
            }

            if (!result) {
                throw new Error('Analysis did not return a result. Please retry.');
            }
            setAnalysisEmailNotification(result?.email_notification || null);
            setMessage(`Architecture document generated: ${result.unique_key}`);
            const generatedDocumentId = String(result?.architecture_document_id || '');
            if (generatedDocumentId) {
                setSelectedDocumentId(generatedDocumentId);
                await loadDocumentContext(generatedDocumentId);
                await fetchAll(generatedDocumentId);
            } else {
                await fetchAll();
            }
        } catch (err) {
            const errText = String(err?.message || '');
            if (errText.includes('502') || errText.toLowerCase().includes('bad gateway')) {
                setError('Analysis service is currently warming up (502). Please retry in a few seconds.');
            } else {
                setError(err.message || 'Failed to analyze repository');
            }
        } finally {
            setAnalyzing(false);
            setLoading(false);
        }
    };

    const generateVariantsFromDoc = async () => {
        if (!hasGithubConnected) {
            setError('GitHub account is not connected. Redirecting to Profile page...');
            setTimeout(() => router.push('/profile'), 1200);
            return;
        }
        if (!selectedDocumentId) {
            setError('Select an architecture document.');
            return;
        }
        setLoading(true);
        setError('');
        setMessage('');
        try {
            const result = await apiClient.generateArchitectureVariants({
                architecture_document_id: selectedDocumentId,
                mode: 'auto',
                cost_weight: Number(weightCost),
                scalability_weight: Number(weightScalability),
                performance_weight: Number(weightPerformance),
            });
            setAnalysisEmailNotification(result?.email_notification || null);
            await loadDocumentContext(selectedDocumentId);
            setMessage('Generated 3 architecture variants.');
        } catch (err) {
            setError(err.message || 'Failed to generate variants');
        } finally {
            setLoading(false);
        }
    };

    const openGeneratedWorkflow = (variant) => {
        if (!variant) {
            return;
        }
        setDiffVariantId(variant.id);
        setActiveWorkflowVariantId(variant.id);
        setWorkflowModal({ open: true, type: 'generated', variantId: variant.id });
        setGeneratedWorkflowGraphs((prev) => {
            if (prev[variant.id]) {
                return prev;
            }
            const baseGraph = normalizeArchitectureSketchGraph(architectureGraph || createFallbackBaseGraph());
            const impacted = inferImpactedNodeIdsForVariant(variant, baseGraph);
            const generatedGraph = buildGeneratedVariantGraph(baseGraph, variant, impacted);
            return {
                ...prev,
                [variant.id]: generatedGraph,
            };
        });
    };

    const openOriginalWorkflow = () => {
        if (!architectureGraph) {
            return;
        }
        setWorkflowModal({ open: true, type: 'original', variantId: '' });
    };

    const onDownloadWorkflowReport = async (variant) => {
        if (!variant?.id) {
            return;
        }

        setReportBusyByVariantId((prev) => ({ ...prev, [variant.id]: true }));
        setReportErrorByVariantId((prev) => ({ ...prev, [variant.id]: '' }));
        setMessage('Preparing workflow report...');

        try {
            const created = await apiClient.createVariantWorkflowReport(variant.id, {
                include_official_references: true,
            });
            const reportId = created?.report_id;
            if (!reportId) {
                throw new Error('Workflow report job could not be created.');
            }

            setReportJobsByVariantId((prev) => ({
                ...prev,
                [variant.id]: {
                    reportId,
                    status: created?.status || 'pending',
                },
            }));

            const finalStatus = await pollWorkflowReportUntilDone(reportId);
            setReportJobsByVariantId((prev) => ({
                ...prev,
                [variant.id]: {
                    reportId,
                    status: finalStatus?.status || 'unknown',
                },
            }));

            if (finalStatus?.status !== 'completed') {
                throw new Error(finalStatus?.error_message || 'Workflow report generation failed.');
            }

            const file = await apiClient.downloadVariantWorkflowReportPdf(reportId);
            triggerBrowserDownload(file.blob, file.filename);
            setMessage(`Workflow report downloaded for ${variant.title}.`);
        } catch (err) {
            const errMessage = err?.message || 'Failed to generate workflow report';
            setReportErrorByVariantId((prev) => ({ ...prev, [variant.id]: errMessage }));
            setError(errMessage);
        } finally {
            setReportBusyByVariantId((prev) => ({ ...prev, [variant.id]: false }));
        }
    };

    const closeWorkflowModal = () => {
        setActiveWorkflowVariantId('');
        setWorkflowModal({ open: false, type: 'original', variantId: '' });
    };

    const onSelectHistoryDocument = (doc) => {
        if (!doc?.id) {
            return;
        }
        setSelectedDocumentId(doc.id);
        setHistoryOpen(false);
        setHistoryQuery('');
        setMessage(`Loaded architecture history: ${doc.unique_key}`);
    };

    useEffect(() => {
        if (!workflowModal.open || typeof window === 'undefined') {
            return;
        }

        const onEscape = (event) => {
            if (event.key === 'Escape') {
                closeWorkflowModal();
            }
        };

        window.addEventListener('keydown', onEscape);
        return () => window.removeEventListener('keydown', onEscape);
    }, [workflowModal.open]);

    if (authLoading) {
        return (
            <>
                <Navbar />
                <div className="page-loading"><div className="spinner" /><p>Loading...</p></div>
            </>
        );
    }

    if (!isAuthenticated) {
        return (
            <>
                <Navbar />
                <div className="auth-required">
                    <h2 className="display-title display-md">ACCESS REQUIRED</h2>
                    <p>Please sign in to use System-Architecture.</p>
                    <Link href="/login" className="btn btn-primary">Sign In</Link>
                </div>
            </>
        );
    }

    return (
        <>
            <Navbar />
            <div className="dashboard-page" style={{ padding: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <h1 className="display-title display-md" style={{ margin: 0 }}>System-Architecture</h1>
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => setHistoryOpen(true)}
                        disabled={loading || !documents.length}
                    >
                        History ({documents.length})
                    </button>
                </div>
                <p style={{ marginBottom: '1rem' }}>Runtime telemetry is preferred, static repository analysis is mandatory.</p>
                <div style={{ position: 'relative' }}>
                    <div
                        style={{
                            pointerEvents: analyzing ? 'none' : 'auto',
                            userSelect: analyzing ? 'none' : 'auto',
                            opacity: analyzing ? 0.28 : 1,
                            transition: 'opacity 180ms ease',
                        }}
                    >
                        {error && <div className="dashboard-error">{error}</div>}
                        {!hasGithubConnected && (
                            <div className="dashboard-error">
                                GitHub account is not connected. Please connect it from your profile page before using System-Architecture actions.
                                {' '}
                                <Link href="/profile" className="btn btn-primary" style={{ marginLeft: '0.5rem' }}>Go To Profile</Link>
                            </div>
                        )}
                        {message && <div className="dashboard-success">{message}</div>}
                        {analysisEmailNotification && (
                            <div
                                style={{
                                    border: '1px solid #cbd5e1',
                                    background: '#f8fafc',
                                    padding: '0.7rem 0.85rem',
                                    borderRadius: '8px',
                                    marginBottom: '0.9rem',
                                }}
                            >
                                <p
                                    style={{
                                        margin: 0,
                                        fontWeight: 700,
                                        color: analysisEmailNotification.status === 'sent'
                                            ? '#166534'
                                            : analysisEmailNotification.status === 'will_notify'
                                                ? '#1d4ed8'
                                                : analysisEmailNotification.status === 'failed'
                                                    ? '#b91c1c'
                                                    : '#475569',
                                    }}
                                >
                                    Email Notification: {analysisEmailNotification.status || 'unknown'}
                                </p>
                                <p style={{ margin: '0.28rem 0 0', color: '#475569' }}>
                                    {analysisEmailNotification.message || 'Email notification status unavailable.'}
                                </p>
                            </div>
                        )}

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div style={{ border: '1px solid #ccc', padding: '1rem' }}>
                        <h3>Connected GitHub Installations</h3>
                        <p>Total: {installations.length}</p>
                        <button className="btn btn-secondary" style={{ marginBottom: '0.75rem' }} onClick={syncRepositories} disabled={loading || !installations.length}>
                            Sync Repositories From GitHub
                        </button>
                        <h4>Connected Repositories</h4>
                        <select
                            value={selectedRepositoryId}
                            onChange={(e) => setSelectedRepositoryId(e.target.value)}
                            style={{ width: '100%', padding: '0.5rem' }}
                        >
                            <option value="">Select repository</option>
                            {repositories.map((repo) => (
                                <option key={repo.id} value={repo.id}>{repo.full_name}</option>
                            ))}
                        </select>
                        <button className="btn btn-secondary" style={{ marginTop: '0.75rem' }} onClick={createSnapshot} disabled={loading}>
                            Create Snapshot (Default Branch)
                        </button>
                        {selectedSnapshotId && <p style={{ marginTop: '0.5rem' }}>Snapshot: {selectedSnapshotId}</p>}
                    </div>

                    <div style={{ border: '1px solid #ccc', padding: '1rem' }}>
                        <h3>Optimization Weights</h3>
                        <label>Cost ({weightCost})</label>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={weightCost}
                            onChange={(e) => setWeightCost(clampWeight(e.target.value))}
                            style={{ width: '100%' }}
                        />
                        <label>Scalability ({weightScalability})</label>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={weightScalability}
                            onChange={(e) => setWeightScalability(clampWeight(e.target.value))}
                            style={{ width: '100%' }}
                        />
                        <label>Performance ({weightPerformance})</label>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={weightPerformance}
                            onChange={(e) => setWeightPerformance(clampWeight(e.target.value))}
                            style={{ width: '100%' }}
                        />
                        <p style={{ marginTop: '0.5rem' }}>
                            Sliders are independent. Each can be set from 0 to 100 without changing the others.
                        </p>
                        <label>SDK App Runtime Context</label>
                        <select
                            value={selectedSdkAppSelector}
                            onChange={(e) => setSelectedSdkAppSelector(e.target.value)}
                            style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
                        >
                            <option value="">None (Use All SDK Telemetry)</option>
                            {sdkApps.map((app) => (
                                <option key={app.selector_value} value={app.selector_value}>
                                    {app.app_name} {app.span_count ? `| spans=${app.span_count}` : ''}
                                </option>
                            ))}
                        </select>
                        <p style={{ marginTop: '0.5rem', marginBottom: '0.5rem', color: '#475569' }}>
                            {selectedSdkApp
                                ? `Using focused runtime reasoning context from ${selectedSdkApp.app_name}.`
                                : 'No app selected: analyzer will use all previously ingested SDK runtime data.'}
                        </p>
                        <button className="btn btn-primary" onClick={analyzeAndGenerate} disabled={loading || analyzing}>
                            {analyzing ? 'Analyzing and Generating...' : 'Analyze + Generate Variants'}
                        </button>
                    </div>
                </div>

                <div style={{ border: '1px solid #ccc', padding: '1rem', marginBottom: '1rem' }}>
                    <h3>Architecture History Selection</h3>
                    {!selectedDocumentId ? (
                        <p style={{ marginBottom: '0.75rem' }}>
                            Blank mode is active. Select an item from History to load previous architecture and all related workflow views.
                        </p>
                    ) : (
                        <p style={{ marginBottom: '0.75rem' }}>
                            Selected document: {documents.find((doc) => doc.id === selectedDocumentId)?.unique_key || selectedDocumentId}
                        </p>
                    )}
                    <button className="btn btn-secondary" onClick={() => setHistoryOpen(true)} disabled={!documents.length}>
                        Open History Picker
                    </button>
                    <button className="btn btn-secondary" style={{ marginTop: '0.75rem' }} onClick={generateVariantsFromDoc} disabled={loading}>
                        Generate 3 Architectures
                    </button>
                </div>

                <div style={{ border: '1px solid #ccc', padding: '1rem', marginBottom: '1rem' }}>
                    <h3>Original Architecture 2D Workflow Sketch</h3>
                    {!selectedDocumentId && <p>Select an architecture document to load graph data.</p>}
                    {graphLoading && <p>Loading graph JSON...</p>}
                    {graphError && <div className="dashboard-error">{graphError}</div>}
                    {!graphLoading && architectureGraph && (
                        <>
                            <p>
                                Nodes: {architectureGraph.nodes?.length || 0} | Edges: {architectureGraph.edges?.length || 0} | Layers: {(architectureGraph.layers || []).join(', ')}
                            </p>
                            <p>
                                Graph mode: {architectureGraph.graph_mode || 'ultra'} (always on)
                            </p>

                            <div style={{ marginBottom: '0.75rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.25rem' }}>Variant Diff Mode (heuristic)</label>
                                <select
                                    value={diffVariantId}
                                    onChange={(e) => setDiffVariantId(e.target.value)}
                                    style={{ width: '100%', padding: '0.5rem' }}
                                >
                                    <option value="">No diff highlight</option>
                                    {variants.map((variant) => (
                                        <option key={variant.id} value={variant.id}>{variant.title}</option>
                                    ))}
                                </select>
                                {selectedVariantForDiff && (
                                    <p style={{ marginTop: '0.5rem' }}>
                                        Highlighting likely impacted nodes for: {selectedVariantForDiff.title} ({impactedNodeIds.size} nodes, {highlightedEdgeIds.size} edges)
                                    </p>
                                )}
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <button
                                    type="button"
                                    className="btn btn-primary"
                                    onClick={openOriginalWorkflow}
                                >
                                    Open Original Workflow
                                </button>
                                <p style={{ margin: 0, alignSelf: 'center', color: '#475569' }}>
                                    Opens in responsive popup with pan/zoom and drag.
                                </p>
                            </div>
                        </>
                    )}
                </div>

                <div style={{ border: '1px solid #ccc', padding: '1rem', marginBottom: '1rem' }}>
                    <h3>Generated Architecture Workflow Sketch</h3>
                    <p>Click Workflow on any variant card below to open that workflow in popup view.</p>
                </div>

                <div style={{ border: '1px solid #ccc', padding: '1rem' }}>
                    <h3>Generated Architecture Variants</h3>
                    {!variants.length ? <p>No variants generated yet.</p> : (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1rem' }}>
                            {variants.map((variant) => {
                                const dependencyStopwords = new Set([
                                    'aside', 'async', 'blog', 'blog-generator-demo', 'cache', 'caching', 'concurrent', 'connection',
                                    'component', 'dependency', 'diagram', 'generated', 'generator', 'layout',
                                    'service', 'services', 'system', 'workflow',
                                ]);
                                const dependencyVersionsRaw = variant.variant?.dependency_versions_used || [];
                                const dependencyVersions = dependencyVersionsRaw
                                    .filter((item) => {
                                        const name = String(item?.name || '').trim().toLowerCase();
                                        if (!name) return false;
                                        if (dependencyStopwords.has(name)) return false;
                                        const source = String(item?.source || '').toLowerCase();
                                        const version = String(item?.version || '').toLowerCase();
                                        if (source === 'reasoning_fallback' && version === 'unspecified') return false;
                                        return /^[@a-z0-9][@a-z0-9._/-]*$/.test(name);
                                    })
                                    .filter((item, index, arr) => (
                                        arr.findIndex((x) => String(x?.name || '').toLowerCase() === String(item?.name || '').toLowerCase()) === index
                                    ));
                                const benefits = variant.variant?.benefits_to_use || [];
                                const lowestCost = variant.variant?.lowest_cost_per_month_usd;
                                const reportJob = reportJobsByVariantId[variant.id] || null;
                                const reportBusy = Boolean(reportBusyByVariantId[variant.id]);
                                const reportError = reportErrorByVariantId[variant.id] || '';

                                return (
                                    <div key={variant.id} style={{ border: '1px solid #ddd', padding: '0.75rem' }}>
                                        <h4>{variant.title}</h4>
                                        <p>Variant #{variant.variant_index}</p>
                                        <p>Major changes: {(variant.variant?.major_changes || []).join(', ')}</p>
                                        <p><strong>Lowest monthly cost (Central India, USD):</strong> {formatUsd(lowestCost)}</p>

                                        <div style={{ marginTop: '0.5rem' }}>
                                            <p style={{ marginBottom: '0.25rem' }}><strong>Dependencies + versions</strong></p>
                                            {!dependencyVersions.length ? (
                                                <p style={{ margin: 0 }}>No dependency version mapping available.</p>
                                            ) : (
                                                <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                                                    {dependencyVersions.slice(0, 8).map((item) => (
                                                        <li key={`${variant.id}-${item.name}`}>
                                                            {item.name} {item.version && item.version !== 'unspecified' ? item.version : '(version not pinned)'}
                                                            {item.latest_version && item.latest_version !== item.version ? ` (latest: ${item.latest_version})` : ''}
                                                            {item.version_validation_source ? ` [validated via ${item.version_validation_source}]` : ''}
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>

                                        <div style={{ marginTop: '0.5rem' }}>
                                            <p style={{ marginBottom: '0.25rem' }}><strong>Benefits</strong></p>
                                            {!benefits.length ? (
                                                <p style={{ margin: 0 }}>No benefit summary available.</p>
                                            ) : (
                                                <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                                                    {benefits.slice(0, 5).map((item, index) => (
                                                        <li key={`${variant.id}-benefit-${index}`}>{item}</li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>

                                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                                            <button
                                                type="button"
                                                className="btn btn-primary"
                                                onClick={() => openGeneratedWorkflow(variant)}
                                            >
                                                Workflow
                                            </button>
                                            <button
                                                type="button"
                                                className="btn btn-primary"
                                                onClick={() => onDownloadWorkflowReport(variant)}
                                                disabled={reportBusy}
                                            >
                                                {reportBusy ? 'Generating Report...' : 'Download Report'}
                                            </button>
                                            <button
                                                type="button"
                                                className="btn btn-secondary"
                                                onClick={() => setDiffVariantId(variant.id)}
                                            >
                                                Show Diff Focus
                                            </button>
                                            <Link href={`/alpha-code?variant=${encodeURIComponent(variant.id)}`} className="btn btn-secondary">Plan Deeply</Link>
                                            <Link href={`/alpha-code?variant=${encodeURIComponent(variant.id)}`} className="btn btn-primary">Make Alpha Codebase</Link>
                                        </div>
                                        {reportJob && (
                                            <p style={{ marginTop: '0.5rem', marginBottom: 0, color: '#334155' }}>
                                                Report status: {reportJob.status}
                                            </p>
                                        )}
                                        {reportError && (
                                            <p style={{ marginTop: '0.35rem', marginBottom: 0, color: '#b91c1c' }}>
                                                Report error: {reportError}
                                            </p>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {workflowModal.open && (
                    <div
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(15, 23, 42, 0.6)',
                            zIndex: 1000,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '1rem',
                        }}
                        onClick={closeWorkflowModal}
                    >
                        <div
                            style={{
                                width: 'min(1200px, 96vw)',
                                height: 'min(760px, 88vh)',
                                background: '#ffffff',
                                borderRadius: '12px',
                                border: '1px solid #d1d5db',
                                boxShadow: '0 24px 60px rgba(15, 23, 42, 0.25)',
                                overflow: 'hidden',
                                display: 'flex',
                                flexDirection: 'column',
                            }}
                            onClick={(event) => event.stopPropagation()}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '0.75rem 1rem',
                                    borderBottom: '1px solid #e5e7eb',
                                    background: '#f8fafc',
                                }}
                            >
                                <div>
                                    <h3 style={{ margin: 0, fontSize: '1rem' }}>
                                        {workflowModal.type === 'original'
                                            ? 'Original Repository Workflow'
                                            : `Generated Workflow: ${activeWorkflowVariant?.title || workflowModal.variantId}`}
                                    </h3>
                                    {workflowModal.type === 'generated' && (
                                        <p style={{ margin: '0.2rem 0 0', color: '#475569', fontSize: '0.85rem' }}>
                                            Lowest monthly cost: {formatUsd(activeWorkflowVariant?.variant?.lowest_cost_per_month_usd)}
                                        </p>
                                    )}
                                </div>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={closeWorkflowModal}
                                    aria-label="Close workflow popup"
                                >
                                    X
                                </button>
                            </div>

                            <div style={{ flex: 1, minHeight: 0 }}>
                                {workflowModal.type === 'generated' && !activeGeneratedGraph ? (
                                    <div style={{ padding: '1rem' }}>Preparing generated workflow sketch...</div>
                                ) : (
                                    <ReactFlow
                                        key={`workflow-${workflowModal.type}-${workflowModal.variantId || 'original'}`}
                                        nodes={workflowModal.type === 'original' ? originalNodes : generatedNodes}
                                        edges={workflowModal.type === 'original' ? originalEdges : generatedEdges}
                                        onNodesChange={workflowModal.type === 'original' ? onOriginalNodesChange : onGeneratedNodesChange}
                                        onEdgesChange={workflowModal.type === 'original' ? onOriginalEdgesChange : onGeneratedEdgesChange}
                                        fitView
                                        nodesDraggable
                                        nodesConnectable={false}
                                        elementsSelectable
                                        panOnDrag
                                    >
                                        <MiniMap zoomable pannable />
                                        <Controls showInteractive />
                                        <Background gap={18} size={1} />
                                    </ReactFlow>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {historyOpen && (
                    <div
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(15, 23, 42, 0.6)',
                            zIndex: 1001,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '1rem',
                        }}
                        onClick={() => setHistoryOpen(false)}
                    >
                        <div
                            style={{
                                width: 'min(880px, 96vw)',
                                maxHeight: '86vh',
                                background: '#ffffff',
                                borderRadius: '12px',
                                border: '1px solid #d1d5db',
                                boxShadow: '0 24px 60px rgba(15, 23, 42, 0.25)',
                                overflow: 'hidden',
                                display: 'flex',
                                flexDirection: 'column',
                            }}
                            onClick={(event) => event.stopPropagation()}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', borderBottom: '1px solid #e5e7eb', background: '#f8fafc' }}>
                                <div>
                                    <h3 style={{ margin: 0, fontSize: '1rem' }}>Architecture History</h3>
                                    <p style={{ margin: '0.2rem 0 0', color: '#475569', fontSize: '0.85rem' }}>Select any previous architecture to load its graph and generated workflows.</p>
                                </div>
                                <button type="button" className="btn btn-secondary" onClick={() => setHistoryOpen(false)}>X</button>
                            </div>

                            <div style={{ padding: '0.8rem 1rem', borderBottom: '1px solid #e5e7eb' }}>
                                <input
                                    type="text"
                                    value={historyQuery}
                                    onChange={(e) => setHistoryQuery(e.target.value)}
                                    placeholder="Search by key, repository id, or snapshot id"
                                    style={{ width: '100%', padding: '0.6rem' }}
                                />
                            </div>

                            <div style={{ overflow: 'auto', padding: '0.75rem 1rem' }}>
                                {!filteredHistoryDocuments.length ? (
                                    <p style={{ margin: 0 }}>No matching architecture history entries found.</p>
                                ) : (
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.75rem' }}>
                                        {filteredHistoryDocuments.map((doc, index) => (
                                            <div key={doc.id} style={{ border: '1px solid #d1d5db', padding: '0.75rem', borderRadius: '8px', background: selectedDocumentId === doc.id ? '#eff6ff' : '#ffffff' }}>
                                                <p style={{ margin: 0, fontWeight: 700 }}>{doc.unique_key}</p>
                                                <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: '#475569' }}>History #{index + 1} | Created: {doc.created_at || 'N/A'}</p>
                                                <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: '#475569' }}>Repository: {doc.repository_id} | Snapshot: {doc.snapshot_id}</p>
                                                <button
                                                    type="button"
                                                    className="btn btn-primary"
                                                    style={{ marginTop: '0.6rem' }}
                                                    onClick={() => onSelectHistoryDocument(doc)}
                                                >
                                                    Load Architecture + Workflows
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
                    </div>

                    {analyzing && (
                        <div
                            style={{
                                position: 'absolute',
                                inset: 0,
                                background: 'rgba(10, 15, 27, 0.78)',
                                backdropFilter: 'blur(2px)',
                                zIndex: 60,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: '1rem',
                                borderRadius: '10px',
                            }}
                            aria-live="polite"
                            aria-busy="true"
                        >
                            <div
                                style={{
                                    width: 'min(640px, 95%)',
                                    background: '#fff',
                                    border: '2px solid #111827',
                                    borderRadius: '10px',
                                    padding: '1.25rem',
                                    boxShadow: '0 14px 38px rgba(2, 6, 23, 0.35)',
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                                    <div className="spinner" />
                                    <h3 style={{ margin: 0 }}>Deep Analysis In Progress</h3>
                                </div>

                                <p style={{ margin: '0.25rem 0 0.5rem' }}>
                                    Architecture analysis is running. Page actions are temporarily locked to avoid inconsistent state.
                                </p>

                                <div style={{ marginBottom: '0.5rem', color: '#334155' }}>
                                    {analysisStatusText}
                                </div>

                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '0.5rem' }}>
                                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', padding: '0.5rem' }}>
                                        <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Expected Duration</div>
                                        <div style={{ fontWeight: 700 }}>Takes Up To {ANALYSIS_TAKES_UPTO_MINUTES} min</div>
                                    </div>
                                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', padding: '0.5rem' }}>
                                        <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Running Time</div>
                                        <div style={{ fontWeight: 700 }}>{analysisElapsedSec}s</div>
                                    </div>
                                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', padding: '0.5rem' }}>
                                        <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Attempt</div>
                                        <div style={{ fontWeight: 700 }}>{Math.max(analysisAttempt, 1)} / 2</div>
                                    </div>
                                </div>

                                <div
                                    style={{
                                        height: '8px',
                                        background: '#e2e8f0',
                                        borderRadius: '999px',
                                        overflow: 'hidden',
                                    }}
                                >
                                    <div
                                        style={{
                                            height: '100%',
                                            width: `${20 + ((analysisElapsedSec * 7) % 70)}%`,
                                            background: 'linear-gradient(90deg, #2563eb, #60a5fa)',
                                            transition: 'width 320ms ease',
                                        }}
                                    />
                                </div>

                                <p style={{ margin: '0.6rem 0 0', fontSize: '0.82rem', color: '#475569' }}>
                                    You will get an email notification once architecture generation completes.
                                </p>
                                <p style={{ margin: '0.35rem 0 0', fontSize: '0.82rem', color: '#475569' }}>
                                    Temporary 502 responses can occur while backend workers warm up. This screen will auto-handle a retry.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
