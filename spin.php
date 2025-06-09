<?php
header('Content-Type: application/json');

// Einfache Zufallszahlen 1-9
$roll1 = rand(1, 9);
$roll2 = rand(1, 9);
$roll3 = rand(1, 9);

// Gewinn, wenn alle gleich
$gewonnen = ($roll1 === $roll2 && $roll2 === $roll3);

// JSON-Antwort
$response = [
    'roll1' => $roll1,
    'roll2' => $roll2,
    'roll3' => $roll3,
    'gewonnen' => $gewonnen
];

echo json_encode($response);
?>
