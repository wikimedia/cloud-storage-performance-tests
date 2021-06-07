import React from 'react';
import { TestDataT } from '../../types';
import { makeStyles } from '@material-ui/core';
import { DataEntry } from '../DataEntry';

const useStyles = makeStyles(() => ({
    testTitle: {
        fontWeight: 'bolder',
    },
    testDataBox: {
        paddingLeft: 20,
    }
}));

export function TestData(props: { title: string, test_data: TestDataT }): JSX.Element {
    const classes = useStyles();
    return (
        <div className={classes.testDataBox}>
            <div className={classes.testTitle}>{props.title}:</div>
            <DataEntry label="Host" value={props.test_data.host_info.fqdn}/>
            <DataEntry label="Rack" value={props.test_data.host_info.rack??"no rack"}/>
            <DataEntry label="Is VM" value={(props.test_data.host_info.vm_info === null || props.test_data.host_info.vm_info === undefined)? "no" : "yes"}/>
        </div>
    )
}
