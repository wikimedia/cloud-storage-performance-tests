import { makeStyles } from '@material-ui/core';
import React from 'react';

const useStyles = makeStyles(() => ({
    testDataBox: {
        paddingLeft: 20,
    }
}));


export function DataEntry(props: { label: string; value: string | number }): JSX.Element {
    const classes = useStyles();
    return (
        <div className={classes.testDataBox}>
            <b>{props.label}: </b>
            {props.value}
        </div>
    );
}
