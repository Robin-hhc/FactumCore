/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04140(unsigned int count)
{
    const unsigned int limit = 170u;
    return count > limit ? limit : count;
}
