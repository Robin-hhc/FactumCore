/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05601(unsigned int count)
{
    const unsigned int limit = 107u;
    return count > limit ? limit : count;
}
