'use client'

import React, { useState, useEffect } from 'react';
import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt, useSwitchChain } from 'wagmi';
import { parseEther, formatEther } from 'viem';
import { filecoinCalibration } from 'viem/chains';
import axios, { isAxiosError } from 'axios';
import { toast } from 'sonner';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea"; // Import Textarea for multi-line input
import { getAuthToken } from "@/components/auth/connect-wallet-button";
import { Loader2 } from 'lucide-react'; // Import spinner
import ProvenanceLedgerABI from '@/abi/ProvenanceLedger.json'; // Import ABI

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
const contractAddress = process.env.NEXT_PUBLIC_CONTRACT_ADDRESS as `0x${string}` | undefined;
const filecoinCalibrationChainId = 314159;

export function Inference() {
  const [modelCid, setModelCid] = useState("");
  const [sampleData, setSampleData] = useState(""); // Store as JSON string
  const [inferenceOutput, setInferenceOutput] = useState<string | null>(null); // Renamed: Holds success result or formatted error
  const [isSuccess, setIsSuccess] = useState<boolean | null>(null); // Track if output is success or error
  const [isLoading, setIsLoading] = useState(false);
  const [inferenceError, setInferenceError] = useState<string | null>(null); // For errors related to input/auth
  const [serviceFee, setServiceFee] = useState<bigint | null>(null);
  const [paymentNonce, setPaymentNonce] = useState<string>("");
  const [paymentTxHash, setPaymentTxHash] = useState<`0x${string}` | undefined>(undefined);
  const [isPaying, setIsPaying] = useState(false);
  const [isConfirmingPayment, setIsConfirmingPayment] = useState(false);

  const { address, chain } = useAccount();

  const { chains, switchChain, isPending: isSwitchingChain, error: switchChainError } = useSwitchChain();

  const { data: fetchedFee, isLoading: isFeeLoading, error: feeError } = useReadContract({
    address: contractAddress,
    abi: ProvenanceLedgerABI.abi,
    functionName: 'serviceFee',
    query: { enabled: !!contractAddress },
  });

  const { data: writeContractHash, writeContractAsync, isPending: isWritePending, error: writeError } = useWriteContract();

  const { isLoading: isTxConfirming, isSuccess: isTxSuccess, error: txError } = useWaitForTransactionReceipt({ 
    hash: writeContractHash, 
    query: { enabled: !!writeContractHash }
  });

  // Clear errors when inputs change
  const handleModelCidChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setModelCid(e.target.value);
      setInferenceError(null);
      setInferenceOutput(null); // Clear output on input change
      setIsSuccess(null);
  }
  const handleSampleDataChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setSampleData(e.target.value);
      setInferenceError(null);
      setInferenceOutput(null); // Clear output on input change
      setIsSuccess(null);
  }

  const runInference = async (confirmedTxHash: `0x${string}`, confirmedNonce: string) => {
    const token = getAuthToken();
    if (!token) { /* Already checked */ return; }

    let parsedSampleData;
    try {
      parsedSampleData = JSON.parse(sampleData);
    } catch { /* Already validated */ }
    if (!parsedSampleData) { /* Should not happen */ return; }

    setIsLoading(true); // Indicates backend inference call

    try {
      const response = await axios.post(`${backendUrl}/inference/predict`,
        {
          model_cid: modelCid,
          data: parsedSampleData,
          paymentTxHash: confirmedTxHash, // Include payment info
          paymentNonce: confirmedNonce
        },
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (response.data && response.data.prediction !== undefined) {
        // Display only prediction for simplicity, can adjust later
        setInferenceOutput(JSON.stringify(response.data.prediction, null, 2)); 
        setIsSuccess(true);
        toast.success("Inference successful!");
      } else {
        throw new Error("Inference failed: Invalid response from server.");
      }
    } catch (error: unknown) {
      console.error("Inference error (post-payment):", error);
      let detail = "An unknown error occurred during inference after payment.";
      if (isAxiosError(error)) {
        if (error.response?.status === 402) {
             detail = "Backend payment verification failed. Please check the transaction and try again.";
        } else {
             detail = error.response?.data?.detail || error.message;
        }
      } else if (error instanceof Error) {
        detail = error.message;
      }
      setInferenceOutput(detail); // Show error in output area
      setIsSuccess(false);
      toast.error(`Inference failed: ${detail}`);
    } finally {
      setIsLoading(false);
      // Reset payment state maybe?
      // setPaymentTxHash(undefined);
      // setPaymentNonce("");
    }
  };

  const handleInitiateInference = async () => {
    setInferenceError(null); // Clear previous input errors
    setInferenceOutput(null); // Clear previous output
    setIsSuccess(null);

    if (!modelCid) {
      setInferenceError("Please enter a Model CID.");
      toast.error("Please enter a Model CID.");
      return;
    }
    if (!sampleData) {
      setInferenceError("Please enter sample data (JSON format).");
      toast.error("Please enter sample data (JSON format).");
      return;
    }

    // Check fee loaded
    if (serviceFee === null || serviceFee <= BigInt(0)) {
         const feeMsg = serviceFee === BigInt(0) ? "Service fee is currently zero." : "Service fee not loaded or contract not found.";
         setInferenceError(feeMsg + " Cannot proceed with payment.");
         toast.error(feeMsg);
         return;
    }

    // Reset previous payment attempts
    setPaymentTxHash(undefined);

    // --- Initiate Payment --- 
    setIsPaying(true);
    setInferenceError(null);
    const nonce = Date.now().toString() + Math.random().toString(36).substring(2, 10);
    setPaymentNonce(nonce); // Store nonce for verification later

    console.log(`Initiating inference payment: Fee=${serviceFee}, Nonce=${nonce}`);
    toast.info(`Please confirm the payment of ${formatEther(serviceFee)} FIL in your wallet.`);

    try {
        await writeContractAsync({
            address: contractAddress!,
            abi: ProvenanceLedgerABI.abi,
            functionName: 'payForService',
            args: ["INFERENCE", nonce], // Pass service type and nonce
            value: serviceFee,
            chainId: filecoinCalibrationChainId
        });
        // Handle confirmation in useEffect
        setIsConfirmingPayment(true);
    } catch (error: unknown) {
        console.error("Failed to initiate inference payment transaction:", error);
        const detail = writeError ? writeError.message : (error instanceof Error ? error.message : "Failed to send payment transaction.");
        // Set the output to display the error, mark as not success
        setInferenceError(detail);
        toast.error(`Inference failed: ${detail}`);
        setIsPaying(false);
        setIsConfirmingPayment(false);
        setPaymentNonce("");
    } finally {
        // Ensure paying state is reset even if switchChain fails or user cancels
        setIsPaying(false);
    }
  };

  useEffect(() => {
    if (fetchedFee !== undefined && fetchedFee !== null) {
      setServiceFee(fetchedFee as bigint);
    }
    if (feeError) {
      console.error("Error fetching service fee:", feeError);
      toast.error(`Failed to fetch service fee: ${feeError.message}`);
    }
  }, [fetchedFee, feeError]);

  useEffect(() => {
    if (isTxSuccess && writeContractHash && paymentNonce) {
      toast.success(`Payment transaction confirmed: ${writeContractHash.substring(0,10)}...`);
      setIsConfirmingPayment(false);
      setIsPaying(false);
      // --- Now run inference --- 
      runInference(writeContractHash, paymentNonce);
    } else if (txError) {
      toast.error(`Payment transaction failed: ${txError.message}`);
      setIsConfirmingPayment(false);
      setIsPaying(false);
      setInferenceError("Payment transaction failed."); 
    }
    setIsConfirmingPayment(isTxConfirming); // Update confirming state
  }, [isTxSuccess, txError, writeContractHash, isTxConfirming, paymentNonce]);

  const formattedFee = serviceFee !== null ? formatEther(serviceFee) : "...";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Inference</CardTitle>
        <CardDescription>Query a trained model with sample data.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid w-full max-w-sm items-center gap-1.5">
          <Label htmlFor="model-cid-inference">Model CID</Label>
          <Input
            id="model-cid-inference"
            placeholder="Enter model CID..."
            value={modelCid}
            onChange={handleModelCidChange} // Use specific handler
            disabled={isLoading || isPaying}
          />
        </div>
        <div className="grid w-full items-center gap-1.5">
          <Label htmlFor="sample-data">Sample Data (JSON Format)</Label>
          <Textarea
            id="sample-data"
            placeholder='{ "feature1": 1.0, "feature2": 2.5 }'
            value={sampleData}
            onChange={handleSampleDataChange} // Use specific handler
            disabled={isLoading || isPaying}
            rows={4}
          />
        </div>
        <div className="text-sm text-muted-foreground">
            Inference Service Fee: {isFeeLoading ? "Loading..." : feeError ? "Error loading fee" : `${formattedFee} FIL`}
        </div>
        {/* Display Input/Auth Error */} 
        {inferenceError && (
            <p className="text-sm text-red-600">Error: {inferenceError}</p>
        )}

        {/* Display Inference Result/Error Area */} 
        {inferenceOutput !== null && (
            <div className="mt-4 p-3 border rounded bg-muted/50 min-h-[80px]"> {/* Added min-height */}
                <h4 className="text-sm font-medium mb-1">Inference Result</h4>
                <pre className={`text-sm whitespace-pre-wrap break-words ${isSuccess === false ? 'text-red-600' : ''}`}>
                    {isSuccess === false ? `Error: ${inferenceOutput}` : inferenceOutput}
                </pre>
            </div>
        )}
         {/* Show loading state in result area? Could be an option */} 
         {(isLoading || isPaying) && inferenceOutput === null && (
             <div className="mt-4 p-3 border rounded bg-muted/50 min-h-[80px] flex items-center justify-center">
                 <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                 {isPaying && <span className="ml-2 text-muted-foreground text-sm">Processing payment...</span>}
                 {isLoading && !isPaying && <span className="ml-2 text-muted-foreground text-sm">Running inference...</span>}
             </div>
         )}
      </CardContent>
      <CardFooter>
        <Button 
            onClick={handleInitiateInference}
            disabled={
                !modelCid || !sampleData || 
                serviceFee === null || isFeeLoading || 
                isPaying || isConfirmingPayment || isWritePending || isTxConfirming || isSwitchingChain ||
                isLoading
            }
        >
            {isSwitchingChain ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Switching Network...</>
            ) : isPaying ? (
                isConfirmingPayment ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Confirming Payment...</> : 
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Paying Fee...</>
            ) : isLoading ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Running Inference...</>
            ) : (
                'Pay Fee & Run Inference'
            )}
        </Button>
      </CardFooter>
    </Card>
  );
} 