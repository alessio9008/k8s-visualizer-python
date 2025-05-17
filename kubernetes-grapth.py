import argparse
from kubernetes import client, config
from graphviz import Digraph


def load_kube_config():
    """
    Load Kubernetes configuration from the default kubeconfig file.
    """
    config.load_kube_config()


def create_graph(format='png', dpi=300, size=13):
    """
    Initialize and return a Graphviz Digraph with layout and size settings.
    """
    dot = Digraph('k8s', format=format)
    dot.attr(rankdir='LR', size=str(size), dpi=str(dpi))
    return dot

# Fetch functions

def fetch_deployments(ns=None):
    api = client.AppsV1Api()
    return api.list_namespaced_deployment(ns).items if ns else api.list_deployment_for_all_namespaces().items


def fetch_statefulsets(ns=None):
    api = client.AppsV1Api()
    return api.list_namespaced_stateful_set(ns).items if ns else api.list_stateful_set_for_all_namespaces().items


def fetch_daemonsets(ns=None):
    api = client.AppsV1Api()
    return api.list_namespaced_daemon_set(ns).items if ns else api.list_daemon_set_for_all_namespaces().items


def fetch_pods(ns=None):
    api = client.CoreV1Api()
    return api.list_namespaced_pod(ns).items if ns else api.list_pod_for_all_namespaces().items


def fetch_services(ns=None):
    api = client.CoreV1Api()
    return api.list_namespaced_service(ns).items if ns else api.list_service_for_all_namespaces().items


def fetch_ingresses(ns=None):
    api = client.NetworkingV1Api()
    return api.list_namespaced_ingress(ns).items if ns else api.list_ingress_for_all_namespaces().items


def fetch_jobs(ns=None):
    api = client.BatchV1Api()
    return api.list_namespaced_job(ns).items if ns else api.list_job_for_all_namespaces().items


def fetch_cronjobs(ns=None):
    api = client.BatchV1Api()
    return api.list_namespaced_cron_job(ns).items if ns else api.list_cron_job_for_all_namespaces().items

# Add node functions

def add_nodes(dot, items, shape, color, prefix):
    """
    Generic: add nodes for k8s objects with given style.
    """
    for obj in items:
        nid = f"{obj.metadata.namespace}/{obj.metadata.name}"
        dot.node(nid, label=f"{prefix}\n{obj.metadata.name}", shape=shape, style='filled', fillcolor=color)

# Link functions

def link_owner_to_pods(dot, pods, owner_kind, label):
    """
    Link owner objects (ReplicaSet, StatefulSet, DaemonSet, Job) to their Pod children via ownerReferences.
    """
    for pod in pods:
        pod_id = f"{pod.metadata.namespace}/{pod.metadata.name}"
        for owner in pod.metadata.owner_references or []:
            if owner.kind == owner_kind:
                base = '-'.join(owner.name.split('-')[:-1])
                owner_id = f"{pod.metadata.namespace}/{base}" if owner_kind != 'Job' else f"{pod.metadata.namespace}/{owner.name}"
                dot.edge(owner_id, pod_id, label=label)


def link_services_to_pods(dot, services, pods):
    """
    Link Service nodes to Pod nodes.
    - If Service has a selector, match pods by labels.
    - Otherwise, match pods exposing the same targetPort on any container.
    """
    svc_linked=[]

    for svc in services:
        svc_id = f"{svc.metadata.namespace}/{svc.metadata.name}"
        selector = svc.spec.selector or {}
        # Gather possible ports sp.targetPort values
        for pod in pods:
            if pod.metadata.namespace != svc.metadata.namespace:
                continue
            labels = pod.metadata.labels or {}
            # Try matching by selector
            if selector and all(labels.get(k) == v for k, v in selector.items()):
                pod_id = f"{pod.metadata.namespace}/{pod.metadata.name}"
                dot.edge(svc_id, pod_id, label='svc')
                svc_linked.append(svc)

    for svc in services:

        if svc in svc_linked:
            continue

        svc_id = f"{svc.metadata.namespace}/{svc.metadata.name}"
        # Gather possible ports sp.targetPort values
        ports = [p.target_port for p in svc.spec.ports]
        for pod in pods:
            if pod.metadata.namespace != svc.metadata.namespace:
                continue
            # Fallback: match by containerPort
            for container in pod.spec.containers:
                for p in container.ports or []:
                    if p.container_port in ports:
                        pod_id = f"{pod.metadata.namespace}/{pod.metadata.name}"
                        dot.edge(svc_id, pod_id, label='svc')



def link_ingresses_to_services(dot, ingresses):
    """
    Link Ingress objects to Services based on HTTP paths.
    """
    for ing in ingresses:
        ing_id = f"{ing.metadata.namespace}/{ing.metadata.name}"
        for rule in ing.spec.rules or []:
            for path in rule.http.paths:
                svc_id = f"{ing.metadata.namespace}/{path.backend.service.name}"
                dot.edge(ing_id, svc_id, label=path.path)


def link_cronjobs_to_jobs(dot, jobs, cronjobs):
    """
    Link CronJob objects to their Job children via ownerReferences.
    """
    cron_ids = {cj.metadata.uid: f"{cj.metadata.namespace}/{cj.metadata.name}" for cj in cronjobs}
    for job in jobs:
        job_id = f"{job.metadata.namespace}/{job.metadata.name}"
        for owner in job.metadata.owner_references or []:
            if owner.kind == 'CronJob' and owner.uid in cron_ids:
                dot.edge(cron_ids[owner.uid], job_id, label='schedule')

# Main execution

def parse_args():
    parser = argparse.ArgumentParser(description="Generate a K8s cluster graph")
    parser.add_argument('-o', '--output', default='cluster', help='Output file')
    parser.add_argument('-n', '--namespace', default=None, help='Namespace filter')
    return parser.parse_args()


def main():
    args = parse_args()
    load_kube_config()
    ns = args.namespace

    # Fetch resources
    deps = fetch_deployments(ns)
    sts = fetch_statefulsets(ns)
    dss = fetch_daemonsets(ns)
    pods = fetch_pods(ns)
    svcs = fetch_services(ns)
    ings = fetch_ingresses(ns)
    jobs = fetch_jobs(ns)
    cronjobs = fetch_cronjobs(ns)

    # Build graph
    dot = create_graph()
    add_nodes(dot, deps, 'folder', 'lightblue', 'Deployment')
    add_nodes(dot, sts, 'cylinder', 'lightcoral', 'StatefulSet')
    add_nodes(dot, dss, 'box3d', 'lightyellow', 'DaemonSet')
    add_nodes(dot, pods, 'oval', 'white', 'Pod')
    add_nodes(dot, svcs, 'box', 'orange', 'Service')
    add_nodes(dot, ings, 'hexagon', 'lightgreen', 'Ingress')
    add_nodes(dot, jobs, 'diamond', 'plum', 'Job')
    add_nodes(dot, cronjobs, 'parallelogram', 'lightgrey', 'CronJob')

    # Create links
    link_owner_to_pods(dot, pods, 'ReplicaSet', 'replica')
    link_owner_to_pods(dot, pods, 'StatefulSet', 'replica')
    link_owner_to_pods(dot, pods, 'DaemonSet', 'daemon')
    link_owner_to_pods(dot, pods, 'Job', 'job')
    link_services_to_pods(dot, svcs, pods)
    link_ingresses_to_services(dot, ings)
    link_cronjobs_to_jobs(dot, jobs, cronjobs)

    # Render
    out = dot.render(filename=args.output, cleanup=True)
    print(f"Graph generated: {out} (namespace: {ns or 'all'})")

if __name__ == '__main__':
    main()
