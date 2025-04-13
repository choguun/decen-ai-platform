'use client'

import React, { useState, useEffect, useRef } from 'react';
import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt, useSwitchChain } from 'wagmi';
import { parseEther, formatEther } from 'viem'; // For handling ETH values
import { filecoinCalibration } from 'viem/chains'; // Import chain definition
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import ProvenanceLedgerABI from '@/abi/ProvenanceLedger.json'; 

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
const filecoinExplorerTx = 'https://calibration.filscan.io/en/message/';
const lighthouseGateway = 'https://gateway.lighthouse.storage/ipfs/';
const contractAddress = process.env.NEXT_PUBLIC_CONTRACT_ADDRESS as `0x${string}` | undefined;

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

// Type for preview data
interface PreviewData {
    headers: string[];
    rows: string[][];
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
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  // --- New State Variables --- 
  const [modelName, setModelName] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // --- Payment State --- 
  const [serviceFee, setServiceFee] = useState<bigint | null>(null);
  const [paymentNonce, setPaymentNonce] = useState<string>("");
  const [paymentTxHash, setPaymentTxHash] = useState<`0x${string}` | undefined>(undefined);
  const [isPaying, setIsPaying] = useState(false); 
  const [isConfirmingPayment, setIsConfirmingPayment] = useState(false);

  const { address, chain } = useAccount();

  // --- Chain Switch Hook --- 
  const { chains, switchChain, isPending: isSwitchingChain, error: switchChainError } = useSwitchChain();

  // --- Wagmi Hooks --- 
  const { data: fetchedFee, isLoading: isFeeLoading, error: feeError } = useReadContract({
    address: contractAddress,
    abi: ProvenanceLedgerABI.abi, // Assuming ABI JSON has an 'abi' field
    functionName: 'serviceFee',
    query: {
        enabled: !!contractAddress, // Only run if address is defined
    },
  });

  const { data: writeContractHash, writeContractAsync, isPending: isWritePending, error: writeError } = useWriteContract();

  const { isLoading: isTxConfirming, isSuccess: isTxSuccess, error: txError } = useWaitForTransactionReceipt({ 
    hash: writeContractHash, 
    query: { enabled: !!writeContractHash }
  });

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
      if (response.data.status === 'TRAINING_COMPLETE' || response.data.status === 'COMPLETED' || response.data.status === 'FAILED') {
        setIsPolling(false);
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        if (response.data.status === 'TRAINING_COMPLETE') {
             toast.success(`Training job ${currentJobId} complete. Ready for upload.`);
        } else if (response.data.status === 'COMPLETED') {
             toast.success(`Training job ${currentJobId} completed successfully (already uploaded).`)
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

  // --- Effect to update serviceFee state from hook --- 
  useEffect(() => {
    if (fetchedFee !== undefined && fetchedFee !== null) {
        console.log("Service fee fetched:", fetchedFee);
      setServiceFee(fetchedFee as bigint); 
    }
    if (feeError) {
        console.error("Error fetching service fee:", feeError);
        toast.error(`Failed to fetch service fee: ${feeError.message}`);
    }
  }, [fetchedFee, feeError]);

  // --- Effect to handle transaction confirmation and trigger job submission --- 
  useEffect(() => {
    console.log("Tx Confirmation Effect: isTxSuccess=", isTxSuccess, "writeContractHash=", writeContractHash, "paymentNonce=", paymentNonce);
    if (isTxSuccess && writeContractHash && paymentNonce) {
        console.log("Condition met! Calling submitTrainingJob with:", writeContractHash, paymentNonce);
        toast.success(`Payment transaction confirmed: ${writeContractHash.substring(0,10)}...`);
        setPaymentTxHash(writeContractHash); // Store the confirmed hash
        setIsConfirmingPayment(false);
        setIsPaying(false); // Reset paying state on success
        // --- Now submit the job to the backend --- 
        submitTrainingJob(writeContractHash, paymentNonce);
    } else if (txError) {
        console.error("Payment transaction error:", txError);
        toast.error(`Payment transaction failed: ${txError.message}`);
        setIsConfirmingPayment(false);
        setIsPaying(false);
        setSubmitError("Payment transaction failed."); // Show error in the form
    }
    // Update confirming state based on hook
    setIsConfirmingPayment(isTxConfirming);
  }, [isTxSuccess, txError, writeContractHash, isTxConfirming, paymentNonce]); // Added paymentNonce dependency

  // --- Refactored function to submit job *after* payment --- 
  const submitTrainingJob = async (confirmedTxHash: `0x${string}`, confirmedNonce: string) => {
    console.log("submitTrainingJob called with:", confirmedTxHash, confirmedNonce);
    const token = getAuthToken();
    if (!token) { /* Should be checked before payment, but double-check */ return; }

    setIsSubmitting(true); // Now indicates submitting job to backend
    setSubmitError(null);

    let hyperparameters = {};
    if (hyperparametersJson) {
        try {
            hyperparameters = JSON.parse(hyperparametersJson);
        } catch { /* Already validated before payment */ }
    }

    try {
        const payload = {
            dataset_cid: datasetCid,
            model_type: modelType,
            target_column: targetColumn,
            hyperparameters: hyperparameters, 
            paymentTxHash: confirmedTxHash, // Include payment info
            paymentNonce: confirmedNonce
        };
        console.debug("Submitting training job with payload:", payload);

        const response = await axios.post(`${backendUrl}/training/start`,
            payload,
            { headers: { 'Authorization': `Bearer ${token}` } }
        );

        if (response.data && response.data.job_id) {
            const newJobId = response.data.job_id;
            setJobId(newJobId);
            setJobStatus(null);
            setIsPolling(true);
            toast.info(`Training job ${newJobId} submitted.`);
        } else {
            throw new Error("Failed to start training: Invalid response after payment.");
        }
    } catch (error: unknown) {
        console.error("Submit training job error (post-payment):", error);
        let detail = "Failed to submit training job after payment.";
        if (isAxiosError(error)) {
            // Handle specific backend errors like 402 Payment Required again?
            if (error.response?.status === 402) {
                detail = "Backend payment verification failed. Please check the transaction and try again.";
            } else {
                detail = error.response?.data?.detail || error.message;
            }
        } else if (error instanceof Error) {
            detail = error.message;
        }
        setSubmitError(detail);
        toast.error(detail);
    } finally {
        setIsSubmitting(false);
    }
  };

  // --- Function to handle Dataset Preview --- 
  const handlePreviewDataset = async () => {
      if (!datasetCid) {
          toast.error("Please enter a Dataset CID first.");
          return;
      }
      
      setIsPreviewLoading(true);
      setPreviewError(null);
      setPreviewData(null);
      
      const gatewayUrl = `${lighthouseGateway}${datasetCid}`;
      
      try {
          const response = await fetch(gatewayUrl);
          if (!response.ok) {
              throw new Error(`Failed to fetch from gateway: ${response.status} ${response.statusText}`);
          }
          const csvText = await response.text();
          
          // Basic CSV Parsing (can be improved for edge cases like quoted commas)
          const lines = csvText.trim().split('\n');
          if (lines.length === 0) {
              setPreviewData({ headers: [], rows: [] });
              setIsPreviewLoading(false);
              return;
          }
          
          const headers = lines[0].split(',').map(h => h.trim());
          const rows = lines.slice(1).map(line => line.split(',').map(cell => cell.trim()));
          
          setPreviewData({ headers, rows });
          toast.success("Dataset preview loaded.");
          
      } catch (error: unknown) {
           console.error("Dataset preview error:", error);
           let detail = "Failed to load dataset preview."
           if (error instanceof Error) {
               detail = error.message;
           }
           setPreviewError(detail);
           toast.error(detail);
      } finally {
           setIsPreviewLoading(false);
      }
  };

  // --- Modified function to initiate payment first --- 
  const handleInitiateTraining = async () => {
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

    // Validate hyperparameters JSON format *before* payment
    let hyperparameters = {}; 
    if (hyperparametersJson) {
        try {
            hyperparameters = JSON.parse(hyperparametersJson);
        } catch { /* Already validated before payment */ }
    }

    // Check if service fee is loaded and > 0
    if (serviceFee === null || serviceFee <= BigInt(0)) {
         const feeMsg = serviceFee === BigInt(0) ? "Service fee is currently zero." : "Service fee not loaded or contract not found.";
         setSubmitError(feeMsg + " Cannot proceed with payment.");
         toast.error(feeMsg);
         return;
    }

    setIsSubmitting(true); // Indicate validation phase before payment
    setSubmitError(null);
    setStatusError(null);
    setJobId(null);
    setJobStatus(null);
    setIsPolling(false); // Ensure polling stops
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current); 
    // Reset previous payment attempts
    setPaymentTxHash(undefined);
    // Reset upload state as well when starting new training
    setIsUploading(false);
    setUploadError(null);
    setModelName("");
    
    // --- Check Network --- 
    if (chain?.id !== filecoinCalibration.id) {
        toast.info("Please switch to Filecoin Calibration network.");
        try {
            // Use the switchChain function from the hook
            await switchChain({ chainId: filecoinCalibration.id });
            // If switch is successful, the rest of the logic will proceed
            // because the component re-renders and this function might be called again
            // OR the user clicks again. We reset state here.
            toast.success("Network switched successfully. Please click 'Pay Fee' again.");
        } catch (switchError: any) {
            console.error("Failed to switch chain:", switchError);
            toast.error(`Failed to switch network: ${switchError.message || 'Unknown error'}`);
        } finally {
             // Reset states regardless of switch success/failure to allow retry
            setIsSubmitting(false);
            setIsPaying(false);
        }
         return; // Stop execution after attempting switch
    }
    
    // --- Initiate Payment --- 
    setIsPaying(true);
    setIsSubmitting(false); // No longer submitting to backend yet
    setSubmitError(null);
    const nonce = Date.now().toString() + Math.random().toString(36).substring(2, 10);
    setPaymentNonce(nonce); // Store nonce for verification later

    console.log(`Initiating payment: Fee=${serviceFee}, Nonce=${nonce}`);
    toast.info(`Please confirm the payment of ${formatEther(serviceFee)} FIL in your wallet.`);

    try {
        await writeContractAsync({
            address: contractAddress!,
            abi: ProvenanceLedgerABI.abi,
            functionName: 'payForService',
            args: ["TRAINING", nonce], // Pass service type and nonce
            value: serviceFee, // Send the fee
            chainId: filecoinCalibration.id // Explicitly set the chain ID
        });
        // writeContractAsync only submits, success/error handled by useEffect watching useWaitForTransactionReceipt
        // Update state to show confirmation is pending
        setIsConfirmingPayment(true);
        setSubmitError(null);
    } catch (error: unknown) {
        console.error("Failed to initiate payment transaction:", error);
        // Use error.message safely
        const detail = writeError ? writeError.message : (error instanceof Error ? error.message : "Failed to send payment transaction.");
        setSubmitError(detail);
        toast.error(`Payment failed: ${detail}`);
        setIsPaying(false); // Reset paying state
        setIsConfirmingPayment(false);
        setPaymentNonce(""); // Clear nonce on failure to send
    } finally {
        // Ensure paying state is reset even if switchChain fails or user cancels
        setIsPaying(false);
        setIsSubmitting(false); // Also reset this, as it was set briefly
    }
  };

  // Helper to determine Badge variant based on status
  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
      switch (status.toUpperCase()) {
          case 'COMPLETED': return 'default';
          case 'TRAINING_COMPLETE': return 'outline';
          case 'PENDING':
          case 'DOWNLOADING':
          case 'TRAINING':
          case 'UPLOADING_MODEL': return 'secondary';
          case 'FAILED':
          case 'ERROR':
          case 'UPLOAD_FAILED': return 'destructive';
          default: return 'outline';
      }
  };

  // Placeholder for the new upload function
  const handleUploadModel = async () => {
      if (!jobId) {
          toast.error("No completed training job found.");
          setUploadError("Cannot upload: No Job ID.");
          return;
      }
      // Model name is optional now
      // if (!modelName) {
      //     toast.error("Please provide a name for the model.");
      //     setUploadError("Model name is required.");
      //     return;
      // }

      const token = getAuthToken();
      if (!token) {
          toast.error("Authentication required.");
          setUploadError("Please sign in first.");
          return;
      }

      setIsUploading(true);
      setUploadError(null);
      toast.info(`Uploading model for job ${jobId}...`);

      // --- API Call to Upload/Register Endpoint --- 
      try {
          const response = await axios.post(`${backendUrl}/models/${jobId}/upload`,
             { model_name: modelName || undefined }, // Send optional model name (null/undefined if empty)
             { headers: { 'Authorization': `Bearer ${token}` } }
          );

          // Update job status based on the *final* status from the upload endpoint response
          // We fetch the full status again to ensure consistency
          fetchJobStatus(jobId);

          toast.success(response.data.message || "Model uploaded and registered successfully!");

      } catch (error: unknown) {
          console.error("Upload error:", error);
          let detail = "Failed to upload or register model.";
          if (isAxiosError(error)) {
              detail = error.response?.data?.detail || error.message;
          } else if (error instanceof Error) {
              detail = error.message;
          }
          setUploadError(detail);
          toast.error(`Upload failed: ${detail}`);

          // Update job status to reflect failure (e.g., UPLOAD_FAILED or keep TRAINING_COMPLETE but show error)
          // Option 1: Fetch status again to see if backend updated it to FAILED/UPLOAD_FAILED
          fetchJobStatus(jobId);
          // Option 2: Manually set a message on the current status (might be overwritten by fetch)
          // setJobStatus(prev => ({ 
          //     ...(prev || {}), 
          //     status: 'UPLOAD_FAILED', // Or keep TRAINING_COMPLETE
          //     message: detail 
          // }));
      } finally {
          setIsUploading(false);
      }
  };

  // --- Helper to format fee --- 
  const formattedFee = serviceFee !== null ? formatEther(serviceFee) : "...";

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
                <div className="flex space-x-2">
                    <Input
                        id="dataset-cid-train"
                        placeholder="Enter dataset CID..."
                        value={datasetCid}
                        onChange={(e) => { 
                            setDatasetCid(e.target.value); 
                            setSubmitError(null); 
                            setPreviewData(null); // Clear preview if CID changes
                            setPreviewError(null);
                        }}
                        disabled={isSubmitting || isPolling || isPreviewLoading}
                    />
                    <Button 
                        variant="outline" 
                        size="icon" 
                        onClick={handlePreviewDataset} 
                        disabled={!datasetCid || isPreviewLoading || isSubmitting || isPolling}
                        title="Preview Dataset"
                    >
                         {isPreviewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "👁️"} 
                    </Button>
                 </div>
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

         {previewError && (
            <div className="mt-2 p-3 border rounded bg-destructive/10">
                 <p className="text-sm text-destructive">Preview Error: {previewError}</p>
            </div>
         )}
         {previewData && (
            <div className="mt-2">
                 <h5 className="text-sm font-medium mb-1">Dataset Preview (First 10 Rows)</h5>
                 <ScrollArea className="h-[200px] border rounded">
                     <Table className="table-fixed w-full">
                        <TableHeader>
                            <TableRow>
                                {previewData.headers.map((header, index) => (
                                    <TableHead key={index} className="whitespace-nowrap px-2 py-1 truncate">{header}</TableHead>
                                ))}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {previewData.rows.slice(0, 10).map((row, rowIndex) => (
                                <TableRow key={rowIndex}>
                                    {row.map((cell, cellIndex) => (
                                        <TableCell key={cellIndex} className="whitespace-nowrap px-2 py-1 truncate" title={cell}>{cell}</TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableBody>
                     </Table>
                 </ScrollArea>
             </div>
         )}
         {isPreviewLoading && !previewError && (
             <div className="mt-2 p-3 border rounded bg-muted/50 flex items-center justify-center min-h-[50px]">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground text-sm">Loading preview...</span>
             </div>
         )}

         {/* --- Display Service Fee --- */}
         <div className="text-sm text-muted-foreground">
             Training Service Fee: {isFeeLoading ? "Loading..." : feeError ? "Error loading fee" : `${formattedFee} FIL`}
         </div>

         {submitError && (
             <p className="text-sm text-red-600">Error: {submitError}</p>
         )}

         {/* --- Job Status Display Area --- */} 
         <div className="mt-4 p-3 border rounded bg-muted/50 min-h-[100px]">
             <h4 className="text-sm font-medium mb-2">
                 Job Status {jobId ? `(${jobId.substring(0,8)}...)` : ""}
             </h4>
             {jobId ? (
                 // Use React Fragment to group multiple elements conditionally
                 <> 
                     {isPolling && !jobStatus && ( 
                         <div className="flex items-center text-sm text-muted-foreground">
                             <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Polling for initial status...
                         </div>
                     )}
                     {jobStatus && (
                         // Display primary status line regardless of detailed status
                         <div className="space-y-1 mb-2">
                             <div className="flex items-center text-sm">
                                 Status: 
                                 <Badge variant={getStatusVariant(jobStatus.status)} className="ml-2"> 
                                     {jobStatus.status}
                                 </Badge>
                                 {isPolling && <Loader2 className="ml-2 h-3 w-3 animate-spin text-muted-foreground" />} 
                             </div>
                             {/* Display general messages unless completed/ready for upload */}
                             {jobStatus.message && jobStatus.status !== 'COMPLETED' && jobStatus.status !== 'TRAINING_COMPLETE' && (
                                 <p className={`text-xs ${jobStatus.status === 'FAILED' || jobStatus.status === 'ERROR' || jobStatus.status === 'UPLOAD_FAILED' ? 'text-red-600' : 'text-muted-foreground'}`}>
                                     {jobStatus.message}
                                 </p>
                             )}
                         </div>
                     )}

                     {/* --- Conditionally Render Upload Section --- */} 
                     {jobStatus && jobStatus.status === 'TRAINING_COMPLETE' && (
                         <div className="mt-3 pt-3 border-t border-dashed space-y-3">
                             <p className="text-sm font-medium text-green-700 dark:text-green-400">Training complete. Ready to upload and register.</p>
                             {/* Model Name Input */} 
                             <div className="space-y-1.5">
                                 <Label htmlFor="model-name">Model Name (Optional)</Label>
                                 <Input
                                     id="model-name"
                                     placeholder="Give your trained model a name..."
                                     value={modelName}
                                     onChange={(e) => { setModelName(e.target.value); setUploadError(null); }}
                                     disabled={isUploading}
                                 />
                             </div>
                             {/* Upload Error Display */} 
                             {uploadError && (
                                 <p className="text-sm text-red-600">Upload Error: {uploadError}</p>
                             )}
                             {/* Upload Button */} 
                             <Button
                                 onClick={handleUploadModel}
                                 disabled={isUploading || jobStatus.status !== 'TRAINING_COMPLETE'}
                                 size="sm"
                             >
                                 {isUploading ? (
                                     <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Uploading...</>
                                 ) : (
                                     'Upload & Register Model'
                                 )}
                             </Button>
                         </div>
                     )}

                     {/* --- Display Final Results only on COMPLETED --- */} 
                     {jobStatus && jobStatus.status === 'COMPLETED' && (
                         <div className="text-xs mt-2 space-y-0.5 pt-2 border-t border-dashed">
                             <p><strong>Model CID:</strong> {jobStatus.model_cid || 'N/A'}</p>
                             <p><strong>Info CID:</strong> {jobStatus.model_info_cid || 'N/A'}</p>
                             <p><strong>Accuracy:</strong> {jobStatus.accuracy ? jobStatus.accuracy.toFixed(4) : 'N/A'}</p>
                             <p><strong>FVM Tx:</strong> 
                                 {jobStatus.fvm_tx_hash ? (
                                     <a href={`${filecoinExplorerTx}${jobStatus.fvm_tx_hash}`} target="_blank" rel="noopener noreferrer" title={jobStatus.fvm_tx_hash} className="inline-flex items-center gap-1 hover:underline text-blue-600 dark:text-blue-400">
                                         {`${jobStatus.fvm_tx_hash.substring(0,10)}...${jobStatus.fvm_tx_hash.substring(jobStatus.fvm_tx_hash.length - 8)}`}
                                         <ExternalLink className="h-3 w-3" />
                                     </a>
                                 ) : (
                                     'N/A'
                                 )}
                             </p>
                         </div>
                     )}

                    {/* Display Status Update Error if applicable */}
                     {statusError && (!jobStatus || (jobStatus.status !== 'FAILED' && jobStatus.status !== 'ERROR' && jobStatus.status !== 'UPLOAD_FAILED')) && (
                         <p className="text-sm text-red-600 mt-2">Status Update Error: {statusError}</p>
                     )}
                 </> // End React Fragment for conditional jobId content
             ) : (
                 // Message when no job is active
                 <p className="text-sm text-muted-foreground">No active training job.</p>
             )}
         </div>
      </CardContent>
      {/* --- Card Footer --- */} 
      <CardFooter>
        <Button 
            onClick={handleInitiateTraining} // Changed onClick handler
            disabled={
                !datasetCid || !modelType || !targetColumn || 
                serviceFee === null || isFeeLoading || 
                isPaying || isConfirmingPayment || isWritePending || isTxConfirming || isSwitchingChain ||
                isSubmitting || isPolling || 
                jobStatus?.status === 'TRAINING_COMPLETE' || 
                isUploading
            }
        >
            {/* Update Button Text based on state */}
            {isSwitchingChain ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Switching Network...</>
            ) : isPaying ? (
                isConfirmingPayment ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Confirming Payment...</> : 
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Paying Fee...</>
            ) : isSubmitting ? (
               <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting Job...</>
            ) : (
                // Show specific status during polling/background processing
                isPolling ? (
                    jobStatus?.status === 'VERIFYING_PAYMENT' ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Verifying Payment...</> :
                    jobStatus?.status === 'DOWNLOADING' ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Downloading Data...</> :
                    jobStatus?.status === 'TRAINING' ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Training Model...</> :
                    'Processing...' // Fallback while polling
                ) : 
                jobStatus?.status === 'TRAINING_COMPLETE' ? 'Training Complete' : // Indicate completion if button is visible but disabled
                isUploading ? 'Uploading Model...' : // Indicate upload in progress
                'Pay Fee & Start Training' // Updated default text
            )}
        </Button>
      </CardFooter>
    </Card>
  );
} 