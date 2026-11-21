/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01156(unsigned int count)
{
    const unsigned int limit = 238u;
    return count > limit ? limit : count;
}
