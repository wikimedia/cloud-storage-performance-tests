import React from 'react';
import { ReportT } from '../../types';
import { makeStyles } from '@material-ui/core';
import { ReportMetadata } from '../ReportMetadata';

const useStyles = makeStyles(() => ({
    selectReport: {
        position: 'absolute',
        left: '500px',
        down: '200px',
        fontSize: '100px',
    },
    progress: {
        position: 'absolute',
        top: 70,
        left: 500,
        zIndex: 0,
        width: '50%',
    },
    detailsRoot: {
        position: 'absolute',
        left: 50,
        height: '100%',
        width: '100%',
    },
    iframe: {
        height: '100%',
        zIndex: 5,
        width: '100%',
        position: 'absolute',
        top: 50,
    },
}));

export function ReportDetails(props: { report: ReportT | null | undefined; loading: boolean }): JSX.Element {
    const classes = useStyles();

    if (props.report == undefined || props.report === null) {
        return <div className={classes.selectReport}>Select a report.</div>;
    }
    return (
        <div className={classes.detailsRoot}>
            {props.loading ? (
                <div className={classes.progress}>Loading... hold your unicorns</div>
            ) : (
                <div>
                    <ReportMetadata report={props.report} />
                    <iframe className={classes.iframe} src={props.report.url} />
                </div>
            )}
        </div>
    );
}
