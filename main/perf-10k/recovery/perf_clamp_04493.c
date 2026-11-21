/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04493(unsigned int count)
{
    const unsigned int limit = 195u;
    return count > limit ? limit : count;
}
