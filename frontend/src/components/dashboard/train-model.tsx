'use client'

import React, { useState, useEffect, useRef } from 'react';
import axios, { isAxiosError } from 'axios';
import { toast } from 'sonner';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { getAuthToken } from "@/components/auth/connect-wallet-button";
import { Loader2, ExternalLink } from 'lucide-react';

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
const filecoinExplorerTx = 'https://calibration.filscan.io/en/message/';

// --- Type Definition ---
interface TrainingStatus {
  job_id: string;
  status: string;
  message?: string;
  dataset_cid: string;
  owner_address: string;
  model_cid?: string;
  model_info_cid?: string;
  accuracy?: number;
  fvm_tx_hash?: string;
  created_at?: string;
  updated_at?: string;
}

export function TrainModel() {
  const [datasetCid, setDatasetCid] = useState("");
  const [modelType, setModelType] = useState<string>("");
  const [targetColumn, setTargetColumn] = useState<string>("");
  const [hyperparametersJson, setHyperparametersJson] = useState<string>("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<TrainingStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Function to fetch job status
  const fetchJobStatus = async (currentJobId: string) => {
    const token = getAuthToken();
    if (!token) return;
    setStatusError(null);

    try {
      const response = await axios.get(`${backendUrl}/training/status/${currentJobId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      setJobStatus(response.data);
      if (response.data.status === 'COMPLETED' || response.data.status === 'FAILED') {
        setIsPolling(false);
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        if (response.data.status === 'COMPLETED') {
             toast.success(`Training job ${currentJobId} completed! Model CID: ${response.data.model_cid}`)
        } else {
             toast.error(`Training job ${currentJobId} failed: ${response.data.message || 'Unknown error'}`)
             setStatusError(response.data.message || 'Training job failed with unknown error');
        }
      }
    } catch (error: unknown) {
      console.error(`Error fetching status for job ${currentJobId}:`, error);
      setIsPolling(false);
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
       let detail = "Failed to fetch job status."
      if (isAxiosError(error)) {
        if (error.response?.status === 404) {
            detail = `Job ${currentJobId} not found.`
        } else {
            detail = error.response?.data?.detail || error.message
        }
      } else if (error instanceof Error) {
        detail = error.message
      }
      toast.error(detail);
      setStatusError(detail);
      setJobStatus(prevStatus => ({
           ...(prevStatus || {}),
           job_id: currentJobId,
           status: 'ERROR',
           message: detail,
           dataset_cid: prevStatus?.dataset_cid || datasetCid,
           owner_address: prevStatus?.owner_address || ''
        }));
    }
  };

  useEffect(() => {
    if (jobId && isPolling) {
        fetchJobStatus(jobId);
        pollIntervalRef.current = setInterval(() => {
            fetchJobStatus(jobId);
        }, 5000);
    } else {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    }
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, isPolling]);

  const handleStartTraining = async () => {
    if (!datasetCid) {
      setSubmitError("Please enter a Dataset CID.");
      toast.error("Please enter a Dataset CID.");
      return;
    }
    if (!modelType) {
      setSubmitError("Please select a Model Type.");
      toast.error("Please select a Model Type.");
      return;
    }
    if (!targetColumn) {
      setSubmitError("Please enter the Target Column name.");
      toast.error("Please enter the Target Column name.");
      return;
    }

    let hyperparameters = {};
    if (hyperparametersJson) {
        try {
            hyperparameters = JSON.parse(hyperparametersJson);
            if (typeof hyperparameters !== 'object' || hyperparameters === null || Array.isArray(hyperparameters)) {
                throw new Error("Hyperparameters must be a valid JSON object.");
            }
        } catch (e: any) {
            const errorMsg = e instanceof Error ? e.message : "Invalid JSON format for Hyperparameters.";
            setSubmitError(errorMsg);
            toast.error(errorMsg);
            return;
        }
    }

    const token = getAuthToken();
    if (!token) {
      setSubmitError("Authentication required. Please sign in.");
      toast.error("Please sign in first.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    setStatusError(null);
    setJobId(null);
    setJobStatus(null);
    setIsPolling(false);
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    try {
      const payload = {
          dataset_cid: datasetCid,
          model_type: modelType,
          target_column: targetColumn,
          hyperparameters: hyperparameters, 
      };
      console.debug("Submitting training job with payload:", payload);

      const response = await axios.post(`${backendUrl}/training/start`,
        payload,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      if (response.data && response.data.job_id) {
        const newJobId = response.data.job_id;
        setJobId(newJobId);
        setJobStatus(null);
        setIsPolling(true);
        toast.info(`Training job ${newJobId} submitted.`);
      } else {
         throw new Error("Failed to start training: Invalid response.");
      }
    } catch (error: unknown) {
      console.error("Start training error:", error);
       let detail = "Failed to start training job."
      if (isAxiosError(error)) {
        detail = error.response?.data?.detail || error.message
      } else if (error instanceof Error) {
        detail = error.message
      }
      setSubmitError(detail);
      toast.error(detail);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Helper to determine Badge variant based on status
  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
      switch (status.toUpperCase()) {
          case 'COMPLETED': return 'default';
          case 'PENDING':
          case 'DOWNLOADING':
          case 'TRAINING':
          case 'UPLOADING_MODEL': return 'secondary';
          case 'FAILED':
          case 'ERROR': return 'destructive';
          default: return 'outline';
      }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Train Model</CardTitle>
        <CardDescription>Configure and start a model training job.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
                <Label htmlFor="dataset-cid-train">Dataset CID</Label>
                <Input
                    id="dataset-cid-train"
                    placeholder="Enter dataset CID..."
                    value={datasetCid}
                    onChange={(e) => { setDatasetCid(e.target.value); setSubmitError(null); }}
                    disabled={isSubmitting || isPolling}
                />
            </div>

            <div className="space-y-1.5">
                 <Label htmlFor="model-type">Model Type</Label>
                 <Select 
                    value={modelType} 
                    onValueChange={(value: string) => { setModelType(value); setSubmitError(null); }} 
                    disabled={isSubmitting || isPolling}
                >
                    <SelectTrigger id="model-type">
                        <SelectValue placeholder="Select a model..." />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="RandomForest">Random Forest</SelectItem>
                        <SelectItem value="XGBoost">XGBoost</SelectItem>
                        <SelectItem value="LogisticRegression">Logistic Regression</SelectItem>
                    </SelectContent>
                </Select>
            </div>

             <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="target-column">Target Column Name</Label>
                <Input
                    id="target-column"
                    placeholder="Enter the exact name of the target variable column..."
                    value={targetColumn}
                    onChange={(e) => { setTargetColumn(e.target.value); setSubmitError(null); }}
                    disabled={isSubmitting || isPolling}
                 />
            </div>

            <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="hyperparameters">Hyperparameters (JSON format, optional)</Label>
                <Textarea
                    id="hyperparameters"
                    placeholder='{ "n_estimators": 100, "max_depth": 5 }'
                    value={hyperparametersJson}
                    onChange={(e) => { setHyperparametersJson(e.target.value); setSubmitError(null); }}
                    disabled={isSubmitting || isPolling}
                    rows={4}
                />
                <p className="text-xs text-muted-foreground">
                    Enter parameters as a JSON object, e.g., {`{"n_estimators": 100}`}.
                </p>
            </div>
        </div>

         {submitError && (
             <p className="text-sm text-red-600">Error: {submitError}</p>
         )}

         <div className="mt-4 p-3 border rounded bg-muted/50 min-h-[100px]">
             <h4 className="text-sm font-medium mb-2">
                 Job Status {jobId ? `(${jobId.substring(0,8)}...)` : ""}
             </h4>
             {jobId ? (
                 <> 
                 {isPolling && !jobStatus && ( 
                    <div className="flex items-center text-sm text-muted-foreground">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Polling for initial status...
                    </div>
                 )}
                 {jobStatus && (
                    <div className="space-y-1">
                        <div className="flex items-center text-sm">
                             Status: 
                             <Badge variant={getStatusVariant(jobStatus.status)} className="ml-2"> 
                                 {jobStatus.status}
                             </Badge>
                             {isPolling && <Loader2 className="ml-2 h-3 w-3 animate-spin text-muted-foreground" />} 
                        </div>
                        {jobStatus.message && jobStatus.status !== 'COMPLETED' && (
                            <p className={`text-xs ${jobStatus.status === 'FAILED' || jobStatus.status === 'ERROR' ? 'text-red-600' : 'text-muted-foreground'}`}>
                                {jobStatus.message}
                            </p>
                        )}
                        {jobStatus.status === 'COMPLETED' && (
                            <div className="text-xs mt-1 space-y-0.5 pt-1 border-t border-dashed">
                                <p><strong>Model CID:</strong> {jobStatus.model_cid || 'N/A'}</p>
                                <p><strong>Info CID:</strong> {jobStatus.model_info_cid || 'N/A'}</p>
                                <p><strong>Accuracy:</strong> {jobStatus.accuracy ? jobStatus.accuracy.toFixed(4) : 'N/A'}</p>
                                <p><strong>FVM Tx:</strong> 
                                    {jobStatus.fvm_tx_hash ? (
                                        <a href={`${filecoinExplorerTx}${jobStatus.fvm_tx_hash}`} target="_blank" rel="noopener noreferrer" title={jobStatus.fvm_tx_hash} className="inline-flex items-center gap-1 hover:underline text-blue-600">
                                            {`${jobStatus.fvm_tx_hash.substring(0,10)}...${jobStatus.fvm_tx_hash.substring(jobStatus.fvm_tx_hash.length - 8)}`}
                                            <ExternalLink className="h-3 w-3" />
                                        </a>
                                    ) : (
                                        'N/A'
                                    )}
                                </p>
                            </div>
                        )}
                    </div>
                 )}
                 {statusError && (!jobStatus || (jobStatus.status !== 'FAILED' && jobStatus.status !== 'ERROR')) && (
                      <p className="text-sm text-red-600 mt-2">Status Update Error: {statusError}</p>
                 )}
                 </>
             ) : (
                 <p className="text-sm text-muted-foreground">No active training job.</p>
             )}
         </div>
      </CardContent>
      <CardFooter>
        <Button 
            onClick={handleStartTraining} 
            disabled={!datasetCid || !modelType || !targetColumn || isSubmitting || isPolling}
        >
          {isSubmitting ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting...</>
          ) : (
              isPolling ? 'Training Active...' : 'Start Training' 
          )}
        </Button>
      </CardFooter>
    </Card>
  );
} 