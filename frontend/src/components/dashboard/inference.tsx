'use client'

import React, { useState } from 'react';
import axios, { isAxiosError } from 'axios';
import { toast } from 'sonner';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea"; // Import Textarea for multi-line input
import { getAuthToken } from "@/components/auth/connect-wallet-button";
import { Loader2 } from 'lucide-react'; // Import spinner

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

export function Inference() {
  const [modelCid, setModelCid] = useState("");
  const [sampleData, setSampleData] = useState(""); // Store as JSON string
  const [inferenceOutput, setInferenceOutput] = useState<string | null>(null); // Renamed: Holds success result or formatted error
  const [isSuccess, setIsSuccess] = useState<boolean | null>(null); // Track if output is success or error
  const [isLoading, setIsLoading] = useState(false);
  const [inferenceError, setInferenceError] = useState<string | null>(null); // For errors related to input/auth

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

  const handleInference = async () => {
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

    let parsedSampleData;
    try {
      parsedSampleData = JSON.parse(sampleData);
      // Add basic validation if needed (e.g., check if it's an object/array)
      if (typeof parsedSampleData !== 'object' || parsedSampleData === null) {
        throw new Error("Sample data must be a valid JSON object or array.");
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : "Invalid JSON format for sample data.";
      setInferenceError(errorMsg);
      toast.error(errorMsg);
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setInferenceError("Authentication required. Please sign in.");
      toast.error("Please sign in first.");
      return;
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${backendUrl}/inference/predict`,
        {
          model_cid: modelCid,
          data: parsedSampleData
        },
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.data && response.data.prediction !== undefined) {
        setInferenceOutput(JSON.stringify(response.data.prediction, null, 2));
        setIsSuccess(true);
        toast.success("Inference successful!");
      } else {
        throw new Error("Inference failed: Invalid response from server.");
      }
    } catch (error: unknown) {
      console.error("Inference error:", error);
      let detail = "An unknown error occurred during inference.";
      if (isAxiosError(error)) {
        detail = error.response?.data?.detail || error.message;
      } else if (error instanceof Error) {
        detail = error.message;
      }
      // Set the output to display the error, mark as not success
      setInferenceOutput(detail);
      setIsSuccess(false);
      toast.error(`Inference failed: ${detail}`);
    } finally {
      setIsLoading(false);
    }
  };

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
            disabled={isLoading}
          />
        </div>
        <div className="grid w-full items-center gap-1.5">
          <Label htmlFor="sample-data">Sample Data (JSON Format)</Label>
          <Textarea
            id="sample-data"
            placeholder='{ "feature1": 1.0, "feature2": 2.5 }'
            value={sampleData}
            onChange={handleSampleDataChange} // Use specific handler
            disabled={isLoading}
            rows={4}
          />
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
         {isLoading && inferenceOutput === null && (
             <div className="mt-4 p-3 border rounded bg-muted/50 min-h-[80px] flex items-center justify-center">
                 <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
         )}
      </CardContent>
      <CardFooter>
        <Button onClick={handleInference} disabled={!modelCid || !sampleData || isLoading}>
          {isLoading ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Running Inference...</>
            ) : (
             'Run Inference'
            )}
        </Button>
      </CardFooter>
    </Card>
  );
} 