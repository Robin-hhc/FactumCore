/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08726(unsigned int count)
{
    const unsigned int limit = 195u;
    return count > limit ? limit : count;
}
