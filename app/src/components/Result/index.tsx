import React from 'react';
import { ResultT } from '../../types';
import { TestData } from '../TestData';
import { DataEntry } from '../DataEntry';
import makeStyles from '@material-ui/core/styles/makeStyles';

const useStyles = makeStyles(() => ({
    resultBox: {
        paddingLeft: 20,
    },
    testsBox: {
        paddingLeft: 20,
    },
    testsTitle: {
        fontWeight: 'bold',
    },
}));

export function Result(props: { result: ResultT | undefined | null }): JSX.Element {
    const classes = useStyles();
    return props.result === undefined || props.result === null ? (
        <div>No metadata for result.</div>
    ) : (
        <div className={classes.resultBox}>
            <DataEntry label="Data path" value={props.result.path} />
            <DataEntry label="Run date" value={props.result.metadata.date} />
            <div className={classes.testsBox}>
                <div className={classes.testsTitle}>Tests:</div>
                <TestData title={'Rbd from hypervisor'} test_data={props.result.metadata.tests.rbd_from_hypervisor} />
                <TestData title={'Rbd from OSD'} test_data={props.result.metadata.tests.rbd_from_osd} />
                <TestData title={'VM disk'} test_data={props.result.metadata.tests.vm_disk} />
            </div>
        </div>
    );
}
