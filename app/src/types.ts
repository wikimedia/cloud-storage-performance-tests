export interface TestDataT {
    test_info: {
        num_passes: number;
        stack_level: StackLevelT;
        script: string;
        host: string;
    };
    host_info: {
        fqdn: string;
        model: string;
        rack?: string;
        vm_info?: {
            ID: string;
            Image: string;
            Flavor: string;
            Name: string;
        };
    };
}

export enum StackLevelT {
    rbd_from_osd = "rbd_from_osd",
    rbd_from_hypervisor = "rbd_from_hypervisor",
    vm_disk = "vm_disk",
}

export interface ResultMetadataT {
    date: string;
    site: string;
    tests: {
        [key in StackLevelT]: TestDataT;
    };
}

export interface ResultT {
    path: string;
    metadata: ResultMetadataT;
}

export interface Metadata {
    creation_time: string;
    report_file: string;
    results: {
        before: ResultT;
        after: ResultT;
    };
}

export interface ReportT {
    name: string;
    url: string;
    metadata: Metadata;
}