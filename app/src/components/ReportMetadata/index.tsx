import React from 'react';
import { ReportT } from '../../types';
import { makeStyles } from '@material-ui/core';
import { Result } from '../Result';
import { DataEntry } from '../DataEntry';
import IconButton from '@material-ui/core/IconButton';
import { MenuBook } from '@material-ui/icons';

const useStyles = makeStyles(() => ({
    metadataGroupClosed: {
        backgroundColor: '#373737',
        height: 48,
        display: 'flex',
        flexDirection: 'column',
        position: 'absolute',
        overflowY: 'visible',
        width: "100%",
        zIndex: 6,
    },
    metadataGroupOpen: {
        backgroundColor: '#373737',
        height: 300,
        display: 'flex',
        flexDirection: 'column',
        position: 'absolute',
        overflowY: 'visible',
        width: "100%",
        zIndex: 6,
    },
    metadataGroupInner: {
        display: 'flex',
        flexDirection: 'row',
    },
    reportTitle: {
        fontSize: '20px',
        fontWeight: 'bold',
        alignSelf: 'center',
    },
    reportMetadataBox: {
        display: 'flex',
        flexDirection: 'row',
        marginLeft: 20,
    },
    reportMetadata: {
        display: 'flex',
        flexDirection: 'column',
        marginLeft: 20,
    },
    results: {
        display: 'flex',
        overflowY: 'auto',
    },
    resultBox: {
        display: 'flex',
        flexDirection: 'column',
    },
    resultBoxTitle: {
        fontSize: '18px',
        fontWeight: 'bold',
    },
    iconButton: {
        color: '#fff',
        backgroundColor: '#373737',
    },
    metadata: {
    },
}));

export function ReportMetadata(props: { report: ReportT | null }): JSX.Element {
    const [metadataOpen, setMetadataOpen] = React.useState(false);
    const classes = useStyles(metadataOpen);

    const handleMetadataToggle = () => {
        setMetadataOpen(!metadataOpen);
    };

    return props.report === null || props.report === undefined || props.report.metadata.results === undefined ? (
        <div>No metadata found.</div>
    ) : (
        <div className={metadataOpen? classes.metadataGroupOpen : classes.metadataGroupClosed}>
            <div className={classes.metadataGroupInner}>
            <div>
                <IconButton onClick={handleMetadataToggle} className={classes.iconButton} disableRipple={true}>
                    <MenuBook />
                </IconButton>
            </div>
                <div className={classes.reportMetadataBox} onClick={handleMetadataToggle}>
                    <div className={classes.reportTitle}>Report metadata</div>
                    <div className={classes.reportMetadata}>
                        <DataEntry label="Creation time" value={props.report?.metadata.creation_time} />
                        <DataEntry label="Report file" value={props.report?.metadata.report_file} />
                    </div>
                </div>
                </div>
                <div className={classes.results}>
                    <div className={classes.resultBox}>
                        <div className={classes.resultBoxTitle}>Before:</div>
                        <Result result={props.report?.metadata.results.before} />
                    </div>
                    <div className={classes.resultBox}>
                        <div className={classes.resultBoxTitle}>After:</div>
                        <Result result={props.report?.metadata.results.after} />
                    </div>
            </div>
        </div>
    );
}
