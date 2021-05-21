import React from 'react';
import { ReportsList } from '../ReportsList';
import './styles.css';

export function PerformanceReportsApp(): JSX.Element {
    return (
        <div className="performance-reports-app">
            <ReportsList/>
        </div>
    );
}