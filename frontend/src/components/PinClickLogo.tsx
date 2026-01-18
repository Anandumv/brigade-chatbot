import React from 'react';
import Image from 'next/image';

interface PinClickLogoProps {
    size?: number;
    showText?: boolean;
    className?: string;
    useImage?: boolean;
}

export const PinClickLogo: React.FC<PinClickLogoProps> = ({ 
    size = 40, 
    showText = true,
    className = '',
    useImage = true
}) => {
    const iconSize = size;
    const textSize = size * 0.6;
    
    return (
        <div className={`flex items-center gap-2 ${className}`}>
            {/* Logo Icon - Use PNG image or SVG fallback */}
            {useImage ? (
                <Image
                    src="/logo.png"
                    alt="Pin Click Logo"
                    width={iconSize}
                    height={iconSize}
                    className="flex-shrink-0 object-contain"
                    priority
                />
            ) : (
                <svg
                    width={iconSize}
                    height={iconSize}
                    viewBox="0 0 40 40"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="flex-shrink-0"
                >
                    {/* Orange Arc (top part of pin) */}
                    <path
                        d="M20 8 C 25 8, 30 12, 30 18 C 30 24, 20 32, 20 32 C 20 32, 10 24, 10 18 C 10 12, 15 8, 20 8 Z"
                        fill="#FF6B35"
                        stroke="none"
                    />
                    {/* Blue Checkmark (bottom part of pin) */}
                    <path
                        d="M 18 20 L 22 24 L 26 18"
                        stroke="#0EA5E9"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        fill="none"
                    />
                </svg>
            )}
            
            {/* Text "pin click" */}
            {showText && (
                <span className="text-lg font-medium tracking-tight" style={{ fontSize: `${textSize}px` }}>
                    <span className="text-slate-800">pin</span>
                    <span className="text-blue-500"> click</span>
                </span>
            )}
        </div>
    );
};

// Compact version for small spaces
export const PinClickLogoIcon: React.FC<{ size?: number; className?: string; useImage?: boolean }> = ({ 
    size = 24, 
    className = '',
    useImage = true
}) => {
    if (useImage) {
        return (
            <Image
                src="/logo.png"
                alt="Pin Click Logo"
                width={size}
                height={size}
                className={className}
                priority
            />
        );
    }
    
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 40 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={className}
        >
            {/* Orange Arc */}
            <path
                d="M20 8 C 25 8, 30 12, 30 18 C 30 24, 20 32, 20 32 C 20 32, 10 24, 10 18 C 10 12, 15 8, 20 8 Z"
                fill="#FF6B35"
            />
            {/* Blue Checkmark */}
            <path
                d="M 18 20 L 22 24 L 26 18"
                stroke="#0EA5E9"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
            />
        </svg>
    );
};
