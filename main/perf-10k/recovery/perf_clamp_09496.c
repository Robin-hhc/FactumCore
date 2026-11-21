/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09496(unsigned int count)
{
    const unsigned int limit = 88u;
    return count > limit ? limit : count;
}
